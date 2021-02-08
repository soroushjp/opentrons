import logging
import contextlib
from typing import Set, Dict, Any, Union, List, TYPE_CHECKING

from opentrons.hardware_control import Pipette
from opentrons.hardware_control.util import plan_arc
from opentrons.hardware_control.types import CriticalPoint
from opentrons.protocol_api import labware
from opentrons.protocols.geometry import planning
from opentrons.protocols.geometry.deck import Deck
from opentrons.calibration_storage import modify, helpers
from opentrons.types import Point, Location

from robot_server.service.errors import RobotServerError
from ...service.session.models.command_definitions import CommandDefinition
from .constants import (
    STATE_WILDCARD, MOVE_TO_REF_POINT_SAFETY_BUFFER,
    TRASH_WELL, TRASH_REF_POINT_OFFSET)
from .errors import CalibrationError
from .tip_length.constants import TipCalibrationState
from .pipette_offset.constants import (
    PipetteOffsetCalibrationState, PipetteOffsetWithTipLengthCalibrationState)
from .deck.constants import DeckCalibrationState
from .check.constants import CalibrationCheckState

if TYPE_CHECKING:
    from .deck.user_flow import DeckCalibrationUserFlow
    from .tip_length.user_flow import TipCalibrationUserFlow
    from .pipette_offset.user_flow import PipetteOffsetCalibrationUserFlow
    from .check.user_flow import CheckCalibrationUserFlow
    from opentrons_shared_data.pipette.dev_types import LabwareUri
    from opentrons_shared_data.labware import LabwareDefinition

ValidState = Union[TipCalibrationState, DeckCalibrationState,
                   PipetteOffsetCalibrationState, CalibrationCheckState,
                   PipetteOffsetWithTipLengthCalibrationState]


class StateTransitionError(RobotServerError):
    def __init__(self,
                 action: CommandDefinition,
                 state: ValidState):
        super().__init__(definition=CalibrationError.BAD_STATE_TRANSITION,
                         action=action,
                         state=state.name)


TransitionMap = Dict[Any, Dict[Any, Any]]
MODULE_LOG = logging.getLogger(__name__)


class SimpleStateMachine:
    def __init__(self,
                 states: Set[Any],
                 transitions: TransitionMap):
        """
        Construct a simple state machine

        :param states: a collection of available states
        :param transitions: the transitions, keyed by "from state",
            with value a dictionary of triggering command to "to state"
        """
        self._states = states
        self._transitions = transitions

    def get_next_state(self, from_state, command):
        """
        Trigger a state transition

        :param from_state: The current state
        :param command: The triggering command
        :param to_state: The desired state
        :return: desired state if successful, None if fails
        """

        wc_transitions = self._transitions.get(STATE_WILDCARD, {})
        wc_to_state = wc_transitions.get(command, {})

        fs_transitions = self._transitions.get(from_state, {})
        fs_to_state = fs_transitions.get(command, {})

        if wc_to_state:
            return wc_to_state
        elif fs_to_state:
            return fs_to_state
        else:
            return None


CalibrationUserFlow = Union[
    'DeckCalibrationUserFlow',
    'TipCalibrationUserFlow',
    'PipetteOffsetCalibrationUserFlow',
    'CheckCalibrationUserFlow']


async def invalidate_tip(user_flow: CalibrationUserFlow):
    await user_flow.return_tip()
    user_flow.reset_tip_origin()
    await user_flow.move_to_tip_rack()


@contextlib.contextmanager
def save_default_pick_up_current(instr: Pipette):
    # reduce pick up current for multichannel pipette picking up 1 tip
    saved_default = instr.config.pick_up_current
    instr.update_config_item('pick_up_current', 0.1)

    try:
        yield
    finally:
        instr.update_config_item('pick_up_current', saved_default)


async def pick_up_tip(user_flow: CalibrationUserFlow, tip_length: float):
    # grab position of active nozzle for ref when returning tip later
    cp = user_flow.critical_point_override
    user_flow.tip_origin = await user_flow.hardware.gantry_position(
        user_flow.mount, critical_point=cp)
    MODULE_LOG.info(f"After tip pick up, tip origin is {user_flow.tip_origin}")
    MODULE_LOG.info(f"The supposed tip length is {tip_length}")

    with contextlib.ExitStack() as stack:
        if user_flow.hw_pipette.config.channels > 1:
            stack.enter_context(
                save_default_pick_up_current(user_flow.hw_pipette))

        await user_flow.hardware.pick_up_tip(user_flow.mount, tip_length)


async def return_tip(user_flow: CalibrationUserFlow, tip_length: float):
    """
    Move pipette with tip to tip rack well, such that
    the tip is inside the well, but not so deep that
    the tip rack will block the sheath from ejecting fully.
    Each pipette config contains a coefficient to apply to an
    attached tip's length to determine proper z offset
    """
    if user_flow.tip_origin and user_flow.hw_pipette.has_tip:
        coeff = user_flow.hw_pipette.config.return_tip_height
        to_pt = user_flow.tip_origin - Point(0, 0, tip_length * coeff)
        cp = user_flow.critical_point_override
        await user_flow.hardware.move_to(mount=user_flow.mount,
                                         abs_position=to_pt,
                                         critical_point=cp)
        await user_flow.hardware.drop_tip(user_flow.mount)
        user_flow.reset_tip_origin()


async def move(user_flow: CalibrationUserFlow,
               to_loc: Location,
               this_move_cp: CriticalPoint = None):
    from_pt = await user_flow.get_current_point(None)
    from_loc = Location(from_pt, None)
    cp = this_move_cp or user_flow.critical_point_override
    MODULE_LOG.info(f"User flow {type(user_flow)}")
    max_height = user_flow.hardware.get_instrument_max_height(
        user_flow.mount)

    safe = planning.safe_height(
        from_loc, to_loc, user_flow.deck, max_height)
    moves = plan_arc(from_pt, to_loc.point, safe,
                     origin_cp=None,
                     dest_cp=cp)
    for move in moves:
        MODULE_LOG.info(f"To abs {move[0]} w/ cp {move[1]}")
        await user_flow.hardware.move_to(mount=user_flow.mount,
                                         abs_position=move[0],
                                         critical_point=move[1])


def get_reference_location(
        deck: Deck,
        cal_block_target_well: labware.Well = None) -> Location:
    """
    Get location of static z reference point.
    Will be on Calibration Block if available, otherwise will be on
    flat surface of fixed trash insert.
    """
    if cal_block_target_well:
        calblock_loc = cal_block_target_well.top()
        ref_loc = calblock_loc.move(point=MOVE_TO_REF_POINT_SAFETY_BUFFER)
    else:
        trash = deck.get_fixed_trash()
        assert trash
        trash_loc = trash.wells_by_name()[TRASH_WELL].top()
        ref_loc = trash_loc.move(TRASH_REF_POINT_OFFSET +
                                 MOVE_TO_REF_POINT_SAFETY_BUFFER)
    return ref_loc


def save_tip_length_calibration(pipette_id: str,
                                tip_length_offset: float,
                                tip_rack: labware.Labware):
    # TODO: 07-22-2020 parent slot is not important when tracking
    # tip length data, hence the empty string, we should remove it
    # from create_tip_length_data in a refactor
    tip_length_data = modify.create_tip_length_data(
        tip_rack._implementation.get_definition(), '',
        tip_length_offset
    )
    modify.save_tip_length_calibration(pipette_id, tip_length_data)


def get_default_tipracks(
        default_uris: List['LabwareUri']) -> List['LabwareDefinition']:
    definitions = []
    for rack in default_uris:
        details = helpers.details_from_uri(rack)
        rack_def = labware.get_labware_definition(
            details.load_name,
            details.namespace,
            details.version)
        definitions.append(rack_def)
    return definitions
