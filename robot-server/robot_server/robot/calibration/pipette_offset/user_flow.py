import logging
from typing import (
    Any, Awaitable, Callable, Dict, List,
    Optional, Union, TYPE_CHECKING, Tuple)

from opentrons.calibration_storage import get, modify, helpers, delete
from opentrons.calibration_storage.types import (
    TipLengthCalNotFound, PipetteOffsetByPipetteMount)
from opentrons.config import feature_flags as ff
from opentrons.hardware_control import (
    ThreadManager, CriticalPoint, Pipette, robot_calibration as robot_cal)
from opentrons.protocol_api import labware
from opentrons.protocols.geometry.deck import Deck
from opentrons.types import Mount, Point, Location
from robot_server.service.errors import RobotServerError
from robot_server.service.session.models.command_definitions import \
    CalibrationCommand
from robot_server.robot.calibration import util
from robot_server.robot.calibration.constants import (
    TIP_RACK_LOOKUP_BY_MAX_VOL,
    SHORT_TRASH_DECK,
    STANDARD_DECK,
    POINT_ONE_ID,
    MOVE_TO_DECK_SAFETY_BUFFER,
    MOVE_TO_TIP_RACK_SAFETY_BUFFER,
    CAL_BLOCK_SETUP_BY_MOUNT,
    JOG_TO_DECK_SLOT)
from ..errors import CalibrationError
from ..helper_classes import (
    RequiredLabware, AttachedPipette, SupportedCommands)
from .constants import (
    PipetteOffsetCalibrationState as POCState,
    PipetteOffsetWithTipLengthCalibrationState as POWTState,
    TIP_RACK_SLOT)
from .state_machine import (
    PipetteOffsetCalibrationStateMachine,
    PipetteOffsetWithTipLengthStateMachine)

if TYPE_CHECKING:
    from opentrons_shared_data.labware import LabwareDefinition


MODULE_LOG = logging.getLogger(__name__)

"""
A collection of functions that allow a consumer to prepare and update
calibration data associated with the position of a specific physical
pipette attached to the gantry, in relation to the deck
"""

# TODO: BC 2020-07-08: type all command logic here with actual Model type
COMMAND_HANDLER = Callable[..., Awaitable]

COMMAND_MAP = Dict[str, COMMAND_HANDLER]
PipetteOffsetStateMachine = Union[
    PipetteOffsetCalibrationStateMachine,
    PipetteOffsetWithTipLengthStateMachine]
PipetteOffsetState = Union[POWTState, POCState]


class PipetteOffsetCalibrationUserFlow:
    def __init__(self,
                 hardware: ThreadManager,
                 mount: Mount = Mount.RIGHT,
                 recalibrate_tip_length: bool = False,
                 has_calibration_block: bool = False,
                 tip_rack_def: Optional['LabwareDefinition'] = None):

        self._hardware = hardware
        self._mount = mount

        self._hw_pipette = self._hardware._attached_instruments[mount]
        if not self._hw_pipette:
            raise RobotServerError(
                definition=CalibrationError.NO_PIPETTE_ON_MOUNT,
                mount=mount)

        deck_load_name = SHORT_TRASH_DECK if ff.short_fixed_trash() \
            else STANDARD_DECK
        self._deck = Deck(load_name=deck_load_name)

        self._saved_offset_this_session = False

        point_one_pos = \
            self._deck.get_calibration_position(POINT_ONE_ID).position
        self._cal_ref_point = Point(*point_one_pos)

        self._tip_origin_pt: Optional[Point] = None
        self._nozzle_height_at_reference: Optional[float] = None

        self._using_default_tiprack = False

        existing_offset_calibration = self._get_stored_pipette_offset_cal()
        self._load_tip_rack(tip_rack_def, existing_offset_calibration)

        existing_tip_length_calibration = self._get_stored_tip_length_cal()
        perform_tip_length = recalibrate_tip_length \
            or not existing_tip_length_calibration

        if perform_tip_length and has_calibration_block:
            self._load_calibration_block()
            self._has_calibration_block = has_calibration_block
        else:
            self._has_calibration_block = False

        self._has_calibrated_tip_length: bool =\
            (self._get_stored_tip_length_cal() is not None
             or self._using_default_tiprack)

        self._sm =\
            self._determine_state_machine(perform_tip_length)

        self._current_state = self._sm.state.sessionStarted

        self._should_perform_tip_length = perform_tip_length

        self._command_map: COMMAND_MAP = {
            CalibrationCommand.load_labware: self.load_labware,
            CalibrationCommand.move_to_reference_point:
                self.move_to_reference_point,
            CalibrationCommand.jog: self.jog,
            CalibrationCommand.pick_up_tip: self.pick_up_tip,
            CalibrationCommand.invalidate_tip: self.invalidate_tip,
            CalibrationCommand.save_offset: self.save_offset,
            CalibrationCommand.move_to_tip_rack: self.move_to_tip_rack,
            CalibrationCommand.move_to_deck: self.move_to_deck,
            CalibrationCommand.move_to_point_one: self.move_to_point_one,
            CalibrationCommand.set_has_calibration_block:
                self.set_has_calibration_block,
            CalibrationCommand.exit: self.exit_session,
            CalibrationCommand.invalidate_last_action:
                self.invalidate_last_action,
        }

        self._hw_pipette.update_pipette_offset(
            robot_cal.load_pipette_offset(pip_id=None, mount=self._mount))
        self._default_tipracks =\
            util.get_default_tipracks(self.hw_pipette.config.default_tipracks)
        self._supported_commands = SupportedCommands(namespace='calibration')
        self._supported_commands.loadLabware = True

    @property
    def deck(self) -> Deck:
        return self._deck

    @property
    def mount(self) -> Mount:
        return self._mount

    @property
    def hardware(self) -> ThreadManager:
        return self._hardware

    @property
    def hw_pipette(self) -> Pipette:
        return self._hw_pipette

    @property
    def current_state(self) -> PipetteOffsetState:
        # Currently, mypy can't interpret enum
        # values being saved as variables. Although
        # using python's built-in typing methods
        # correctly reveals that this is an enum,
        # mypy believes it is a string.
        return self._sm.current_state

    @property
    def has_calibrated_tip_length(self) -> bool:
        return self._has_calibrated_tip_length

    @property
    def should_perform_tip_length(self) -> bool:
        return self._should_perform_tip_length

    @should_perform_tip_length.setter
    def should_perform_tip_length(self, value: bool):
        self._should_perform_tip_length = value

    def get_pipette(self) -> AttachedPipette:
        # TODO(mc, 2020-09-17): s/tip_length/tipLength
        return AttachedPipette(  # type: ignore[call-arg]
            model=self._hw_pipette.model,
            name=self._hw_pipette.name,
            tipLength=self._hw_pipette.config.tip_length,
            mount=str(self._mount),
            serial=self._hw_pipette.pipette_id,
            defaultTipracks=self._default_tipracks  # type: ignore[arg-type]
            )

    def get_required_labware(self) -> List[RequiredLabware]:
        slots = self._deck.get_non_fixture_slots()
        lw_by_slot = {s: self._deck[s] for s in slots if self._deck[s]}
        return [
            RequiredLabware.from_lw(lw, s)  # type: ignore
            for s, lw in lw_by_slot.items()]

    async def set_has_calibration_block(self, hasBlock: bool):
        if self._has_calibration_block and not hasBlock:
            self._remove_calibration_block()
        elif hasBlock and not self._has_calibration_block:
            self._load_calibration_block()
        self._has_calibration_block = hasBlock

    def _get_tip_rack_lw(self) -> labware.Labware:
        pip_vol = self._hw_pipette.config.max_volume
        lw_load_name = TIP_RACK_LOOKUP_BY_MAX_VOL[str(pip_vol)].load_name
        return labware.load(lw_load_name,
                            self._deck.position_for(TIP_RACK_SLOT))

    async def handle_command(self,
                             name: Any,
                             data: Dict[Any, Any]):
        """
        Handle a client command

        :param name: Name of the command
        :param data: Data supplied in command
        :return: None
        """
        # Here we need to get the current state in the state machine's
        # state enum because otherwise mypy will confuse which type
        # the state is.
        state = getattr(self._sm.state, self._sm.current_state)
        next_state = self._sm.get_next_state(state, name)

        handler = self._command_map.get(name)
        if handler is not None:
            await handler(**data)
        self._sm.set_state(next_state)
        MODULE_LOG.debug(
            f'PipetteOffsetCalUserFlow handled command {name}, transitioned'
            f'from {self._sm.current_state} to {next_state}')

    @property
    def critical_point_override(self) -> Optional[CriticalPoint]:
        return (CriticalPoint.FRONT_NOZZLE if
                self._hw_pipette.config.channels == 8 else None)

    async def get_current_point(
            self,
            critical_point: Optional[CriticalPoint]) -> Point:
        return await self._hardware.gantry_position(self._mount,
                                                    critical_point)

    async def load_labware(self, tiprackDefinition: Optional[dict] = None):
        self._supported_commands.loadLabware = False
        if tiprackDefinition:
            verified_definition = labware.verify_definition(tiprackDefinition)
            existing_offset_calibration = self._get_stored_pipette_offset_cal()
            self._load_tip_rack(
                verified_definition,
                existing_offset_calibration)

    async def jog(self, vector):
        await self._hardware.move_rel(mount=self._mount,
                                      delta=Point(*vector))

    @property
    def tip_origin(self) -> Point:
        if self._tip_origin_pt:
            return self._tip_origin_pt
        else:
            return self._tip_rack.wells()[0].top().point +\
                MOVE_TO_TIP_RACK_SAFETY_BUFFER

    @tip_origin.setter
    def tip_origin(self, new_val: Point):
        self._tip_origin_pt = new_val

    def reset_tip_origin(self):
        self._tip_origin_pt = None

    @property
    def supported_commands(self) -> List:
        return self._supported_commands.supported()

    async def move_to_tip_rack(self):
        if self._sm.current_state == self._sm.state.labwareLoaded and \
                not self.has_calibrated_tip_length and\
                not self.should_perform_tip_length:
            self._flag_unmet_transition_req(
                command_handler="move_to_tip_rack",
                unmet_condition="not performing tip length calibration")
        MODULE_LOG.info(f"Tip origin moving to tiprack {self.tip_origin}")
        await self._move(Location(self.tip_origin, None))

    @staticmethod
    def _determine_state_machine(
            perform_tip_length: bool) -> PipetteOffsetStateMachine:
        if perform_tip_length:
            return PipetteOffsetWithTipLengthStateMachine()
        else:
            return PipetteOffsetCalibrationStateMachine()

    def _get_stored_tip_length_cal(self) -> Optional[float]:
        try:
            return get.load_tip_length_calibration(
                self._hw_pipette.pipette_id,
                self._tip_rack._implementation.get_definition(),
                '').tip_length
        except TipLengthCalNotFound:
            return None

    def _get_stored_pipette_offset_cal(
            self) -> Optional[PipetteOffsetByPipetteMount]:
        return get.get_pipette_offset(
            self._hw_pipette.pipette_id, self._mount
        )

    def _get_tip_length(self) -> float:
        stored_tip_length_cal = self._get_stored_tip_length_cal()
        if stored_tip_length_cal is None or self._should_perform_tip_length:
            tip_overlap = self._hw_pipette.config.tip_overlap.get(
                self._tip_rack.uri, 0)
            tip_length = self._tip_rack.tip_length
            return tip_length - tip_overlap
        else:
            return stored_tip_length_cal

    def _load_calibration_block(self):
        cb_setup = CAL_BLOCK_SETUP_BY_MOUNT[self._mount]
        self._deck[cb_setup.slot] = labware.load(
            cb_setup.load_name,
            self._deck.position_for(cb_setup.slot))

    def _remove_calibration_block(self):
        cb_setup = CAL_BLOCK_SETUP_BY_MOUNT[self._mount]
        del self._deck[cb_setup.slot]

    @staticmethod
    def _get_tr_lw(tip_rack_def: Optional['LabwareDefinition'],
                   existing_calibration: Optional[PipetteOffsetByPipetteMount],
                   volume: float,
                   position: Location) -> Tuple[bool, labware.Labware]:
        """ Find the right tiprack to use. Specifically,

        - If it's specified from above, use that
        - If it's not, and we have a calibration, use that
        - If we don't, use the default
        """
        if tip_rack_def:
            return False, labware.load_from_definition(
                tip_rack_def, position)
        if existing_calibration and existing_calibration.uri:
            try:
                details \
                     = helpers.details_from_uri(existing_calibration.uri)
                return True, labware.load(load_name=details.load_name,
                                          namespace=details.namespace,
                                          version=details.version,
                                          parent=position)
            except (IndexError, ValueError, FileNotFoundError):
                pass
        tr_load_name = TIP_RACK_LOOKUP_BY_MAX_VOL[str(volume)].load_name
        return True, labware.load(tr_load_name, position)

    def _load_tip_rack(
            self,
            tip_rack_def: Optional['LabwareDefinition'],
            existing_calibration: Optional[PipetteOffsetByPipetteMount]):
        """
        load onto the deck the default opentrons tip rack labware for this
        pipette and return the tip rack labware. If tip_rack_def is supplied,
        load specific tip rack from def onto the deck and return the labware.
        """
        self._using_default_tiprack, self._tip_rack = self._get_tr_lw(
            tip_rack_def, existing_calibration,
            self._hw_pipette.config.max_volume,
            self._deck.position_for(TIP_RACK_SLOT))
        if self._deck[TIP_RACK_SLOT]:
            del self._deck[TIP_RACK_SLOT]
        self._deck[TIP_RACK_SLOT] = self._tip_rack

    def _flag_unmet_transition_req(self, command_handler: str,
                                   unmet_condition: str):
        raise RobotServerError(
            definition=CalibrationError.UNMET_STATE_TRANSITION_REQ,
            handler=command_handler,
            state=self._sm.current_state,
            condition=unmet_condition)

    async def move_to_deck(self):
        current_state = self._sm.current_state
        if not self.has_calibrated_tip_length and \
                current_state == self._sm.state.inspectingTip:
            self._flag_unmet_transition_req(
                command_handler="move_to_deck",
                unmet_condition="tip length calibration data exists")
        if self.should_perform_tip_length and \
                isinstance(self._sm.state, POWTState) and \
                current_state == self._sm.state.tipLengthComplete and \
                self._saved_offset_this_session:
            self._flag_unmet_transition_req(
                command_handler="move_to_deck",
                unmet_condition="offset not saved this session")
        deck_pt = self._deck.get_slot_center(JOG_TO_DECK_SLOT)
        ydim = self._deck.get_slot_definition(
            JOG_TO_DECK_SLOT)['boundingBox']['yDimension']
        new_pt = deck_pt + Point(0, -1 * ydim/2, 0) + \
            MOVE_TO_DECK_SAFETY_BUFFER
        to_loc = Location(new_pt, None)
        await self._move(to_loc)
        self._should_perform_tip_length = False

    async def move_to_point_one(self):
        assert self._z_height_reference is not None, \
            "saveOffset has not been called yet"
        target_loc = Location(self._cal_ref_point, None)
        target = target_loc.move(
                point=Point(0, 0, self._z_height_reference))
        await self._move(target)

    async def save_offset(self):
        cur_pt = await self.get_current_point(critical_point=None)
        current_state = self._sm.current_state
        if current_state == self._sm.state.joggingToDeck:
            self._z_height_reference = cur_pt.z
        elif current_state == self._sm.state.savingPointOne:
            if self._hw_pipette.config.channels > 1:
                cur_pt = await self.get_current_point(
                    critical_point=CriticalPoint.FRONT_NOZZLE)
            tiprack_hash = helpers.hash_labware_def(
                self._tip_rack._implementation.get_definition())
            offset = self._cal_ref_point - cur_pt
            modify.save_pipette_calibration(
                offset=offset,
                mount=self._mount,
                pip_id=self._hw_pipette.pipette_id,
                tiprack_hash=tiprack_hash,
                tiprack_uri=self._tip_rack.uri)
            self._saved_offset_this_session = True
        elif isinstance(current_state, POWTState)\
                and current_state == POWTState.measuringNozzleOffset:
            self._nozzle_height_at_reference = cur_pt.z
        elif isinstance(current_state, POWTState)\
                and current_state == POWTState.measuringTipOffset:
            assert self._hw_pipette.has_tip
            assert self._nozzle_height_at_reference is not None
            # set critical point explicitly to nozzle
            noz_pt = await self.get_current_point(
                critical_point=CriticalPoint.NOZZLE)

            util.save_tip_length_calibration(
                pipette_id=self._hw_pipette.pipette_id,
                tip_length_offset=noz_pt.z - self._nozzle_height_at_reference,
                tip_rack=self._tip_rack)
            delete.delete_pipette_offset_file(
                self._hw_pipette.pipette_id, self.mount)
            new_tip_length = self._get_stored_tip_length_cal()
            self._has_calibrated_tip_length = new_tip_length is not None
            # load the new tip length for the rest of the session
            self._hw_pipette.current_tip_length = new_tip_length
            await self.hardware.retract(self._mount, 20)

    async def move_to_reference_point(self):
        if not self.should_perform_tip_length and \
                self._sm.current_state in (self._sm.state.labwareLoaded,
                                           self._sm.state.inspectingTip):
            self._flag_unmet_transition_req(
                command_handler="move_to_reference_point",
                unmet_condition="performing additional tip length calibration")
        if self._has_calibration_block:
            cb_setup = CAL_BLOCK_SETUP_BY_MOUNT[self._mount]
            calblock: labware.Labware = \
                self._deck[cb_setup.slot]  # type: ignore
            cal_block_target_well = calblock.wells_by_name()[cb_setup.well]
        else:
            cal_block_target_well = None
        ref_loc = util.get_reference_location(
            deck=self._deck,
            cal_block_target_well=cal_block_target_well)
        await self._move(ref_loc)

    async def invalidate_last_action(self):
        if self._sm.current_state == POWTState.measuringNozzleOffset:
            await self._hardware.home()
            await self._hardware.gantry_position(self.mount, refresh=True)
            await self.move_to_reference_point()
        elif self._sm.current_state == self._sm.state.preparingPipette:
            self.reset_tip_origin()
            await self._hardware.home()
            await self._hardware.gantry_position(self.mount, refresh=True)
            await self.move_to_tip_rack()
        else:
            await self.hardware.home()
            await self._hardware.gantry_position(self.mount, refresh=True)
            trash = self._deck.get_fixed_trash()
            assert trash, 'Bad deck setup'
            await util.move(self, trash['A1'].top(), CriticalPoint.XY_CENTER)
            await self.hardware.drop_tip(self.mount)
            await self.move_to_tip_rack()

    async def pick_up_tip(self):
        await util.pick_up_tip(self, tip_length=self._get_tip_length())

    async def invalidate_tip(self):
        await util.invalidate_tip(self)

    async def return_tip(self):
        await util.return_tip(self, tip_length=self._get_tip_length())

    async def _move(self, to_loc: Location):
        await util.move(self, to_loc)

    async def exit_session(self):
        if self.hw_pipette.has_tip:
            await self.move_to_tip_rack()
            await self.return_tip()
        # reload new pipette offset data by resetting instrument
        self._hardware.reset_instrument(self._mount)
        await self._hardware.home()
