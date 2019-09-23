import logging

from opentrons.commands import CommandPublisher, commands

from opentrons.config.robot_configs import load
from .util import log_call


log = logging.getLogger(__name__)


class Robot(CommandPublisher):
    """
    This class is the main legacy interface to the robot.

    It should never be instantiated directly; instead, the global instance may
    be accessed at :py:attr:`opentrons.robot`.

    Through this class you can can:
        * define your :class:`opentrons.Deck`
        * :meth:`connect` to Opentrons physical robot
        * :meth:`home` axis, move head (:meth:`move_to`)
        * :meth:`pause` and :func:`resume` the protocol run
        * set the :meth:`head_speed` of the robot

    Each Opentrons legacy protocol is a Python script. When evaluated the
    script creates an execution plan which is stored as a list of commands in
    Robot's command queue.

    Here are the typical steps of writing the protocol:
        * Using a Python script and the Opentrons API load your
          containers and define instruments
          (see :class:`~opentrons.instruments.pipette.Pipette`).
        * Call :meth:`reset` to reset the robot's state and clear commands.
        * Write your instructions which will get converted
          into an execution plan.
        * Review the list of commands generated by a protocol
          :meth:`commands`.
        * :meth:`connect` to the robot and call :func:`run` it on a real robot.

    See :class:`Pipette` for the list of supported instructions.
    """

    def __init__(self, config=None, broker=None):
        """
        Initializes a robot instance.

        Notes
        -----
        This class is a singleton. That means every time you call
        :func:`__init__` the same instance will be returned. There's
        only once instance of a robot.
        """
        super().__init__(broker)
        self.config = config or load()

    @log_call(log)
    def clear_tips(self):
        """
        If reset is called with a tip attached, the tip must be removed
        before the poses and _instruments members are cleared. If the tip is
        not removed, the effective length of the pipette remains increased by
        the length of the tip, and subsequent `_add_tip` calls will increase
        the length in addition to this. This should be fixed by changing pose
        tracking to that it tracks the tip as a separate node rather than
        adding and subtracting the tip length to the pipette length.
        """
        return None

    @log_call(log)
    def reset(self):
        """
        Resets the state of the robot and clears:
            * Deck
            * Instruments
            * Command queue
            * Runtime warnings

        Examples
        --------

        >>> from opentrons import robot # doctest: +SKIP
        >>> robot.reset() # doctest: +SKIP
        """
        return None

    @log_call(log)
    def cache_instrument_models(self):
        """
        Queries Smoothie for the model and ID strings of attached pipettes, and
        saves them so they can be reported without querying Smoothie again (as
        this could interrupt a command if done during a run or other movement).

        Shape of return dict should be:

        ```
        {
          "left": {
            "model": "<model_string>" or None,
            "id": "<pipette_id_string>" or None
          },
          "right": {
            "model": "<model_string>" or None,
            "id": "<pipette_id_string>" or None
          }
        }
        ```

        :return: a dict with pipette data (shape described above)
        """
        return None

    @log_call(log)
    def connect(self, port=None, options=None):
        """
        Connects the robot to a serial port.

        Parameters
        ----------
        port : str
            OS-specific port name or ``'Virtual Smoothie'``
        options : dict
            if :attr:`port` is set to ``'Virtual Smoothie'``, provide
            the list of options to be passed to :func:`get_virtual_device`

        Returns
        -------
        ``True`` for success, ``False`` for failure.

        Note
        ----
        If you wish to connect to the robot without using the OT App, you will
        need to use this function.

        Examples
        --------

        >>> from opentrons import robot # doctest: +SKIP
        >>> robot.connect() # doctest: +SKIP
        """
        return None

    @log_call(log)
    def home(self, *args, **kwargs):
        """
        Home robot's head and plunger motors.
        """
        return None

    @log_call(log)
    def home_z(self):
        return None

    @log_call(log)
    def head_speed(
            self, combined_speed=None,
            x=None, y=None, z=None, a=None, b=None, c=None):
        """
        Set the speeds (mm/sec) of the robot

        Parameters
        ----------
        combined_speed : number specifying a combined-axes speed
        <axis> : key/value pair, specifying the maximum speed of that axis

        Examples
        ---------

        >>> from opentrons import robot # doctest: +SKIP
        >>> robot.reset() # doctest: +SKIP
        >>> robot.head_speed(combined_speed=400) # doctest: +SKIP
        #  sets the head speed to 400 mm/sec or the axis max per axis
        >>> robot.head_speed(x=400, y=200) # doctest: +SKIP
        # sets max speeds of X and Y
        """
        return None

    @log_call(log)
    def move_to(
            self,
            location,
            instrument,
            strategy='arc',
            **kwargs):
        """
        Move an instrument to a coordinate, container or a coordinate within
        a container.

        Parameters
        ----------
        location : one of the following:
            1. :class:`Placeable` (i.e. Container, Deck, Slot, Well) — will
            move to the origin of a container.
            2. :class:`Vector` move to the given coordinate in Deck coordinate
            system.
            3. (:class:`Placeable`, :class:`Vector`) move to a given coordinate
            within object's coordinate system.

        instrument :
            Instrument to move relative to. If ``None``, move relative to the
            center of a gantry.

        strategy : {'arc', 'direct'}
            ``arc`` : move to the point using arc trajectory
            avoiding obstacles.

            ``direct`` : move to the point in a straight line.
        """
        return None

    @log_call(log)
    def disconnect(self):
        """
        Disconnects from the robot.
        """
        return None

    @log_call(log)
    def deck(self):
        log.info('robot.deck')
        return None

    @log_call(log)
    def fixed_trash(self):
        log.info('robot.fixed_trash')
        return None

    @log_call(log)
    def get_instruments_by_name(self, name):
        return None

    @log_call(log)
    def get_instruments(self, name=None):
        """
        :returns: sorted list of (mount, instrument)
        """
        return None

    @log_call(log)
    def get_containers(self):
        """
        Returns all containers currently on the deck.
        """
        return None

    @log_call(log)
    def add_container(self, name, slot, label=None, share=False):
        return None

    @log_call(log)
    @commands.publish.both(command=commands.pause)
    def pause(self, msg=None):
        """
        Pauses execution of the protocol. Use :meth:`resume` to resume
        """
        return None

    @log_call(log)
    def execute_pause(self):
        """ Pause the driver

        This method should not be called inside a protocol. Use
        :py:meth:`pause` instead
        """
        return None

    @log_call(log)
    @commands.publish.both(command=commands.resume)
    def resume(self):
        """
        Resume execution of the protocol after :meth:`pause`
        """
        return None

    @log_call(log)
    def is_connected(self):
        return None

    @log_call(log)
    def is_simulating(self):
        return None

    @log_call(log)
    @commands.publish.both(command=commands.comment)
    def comment(self, msg):
        return None

    @log_call(log)
    def commands(self):
        return None

    @log_call(log)
    def clear_commands(self):
        return None

    @property  # type: ignore
    @log_call(log)
    def engaged_axes(self):
        """ Which axes are engaged and holding. """
        return None

    def discover_modules(self):
        pass
