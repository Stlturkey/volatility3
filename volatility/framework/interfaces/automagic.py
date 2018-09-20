"""Defines the automagic interfaces for populating the context before a plugin runs

Automagic objects attempt to automatically fill configuration values that a user has not filled.
"""
import typing
from abc import ABCMeta

import volatility.framework.configuration.requirements
from volatility.framework import validity, interfaces
from volatility.framework.interfaces import configuration as interfaces_configuration

R = typing.TypeVar('R', bound = interfaces.configuration.RequirementInterface)


class AutomagicInterface(interfaces_configuration.ConfigurableInterface, metaclass = ABCMeta):
    """Class that defines an automagic component that can help fulfill a Requirement

    These classes are callable with the following parameters:

    Args:
        context: The context in which to store configuration data that the automagic might populate
        config_path: Configuration path where the configurable's data under the context's config lives
        configurable: The top level configurable whose requirements may need statisfying
        progress_callback: An optional function accepting a percentage and optional description to indicate
            progress during long calculations

    .. note::

        The `context` provided here may be different to that provided during initialization.  The `context` provided at
        initialization should be used for local configuration of the automagic itself, the `context` provided during
        the call is to be populated by the automagic.
    """

    priority = 10
    """An ordering to indicate how soon this automagic should be run"""

    def __init__(self,
                 context: interfaces.context.ContextInterface,
                 config_path: str, *args, **kwargs) -> None:
        super().__init__(context, config_path)
        for requirement in self.get_requirements():
            if not isinstance(requirement, (interfaces_configuration.SimpleTypeRequirement,
                                            volatility.framework.configuration.requirements.ChoiceRequirement,
                                            volatility.framework.configuration.requirements.ListRequirement)):
                raise ValueError(
                    "Automagic requirements must be an SimpleTypeRequirement, ChoiceRequirement or ListRequirement")

    def __call__(self,
                 context: interfaces.context.ContextInterface,
                 config_path: str,
                 requirement: interfaces.configuration.RequirementInterface,
                 progress_callback: validity.ProgressCallback = None) -> typing.Optional[typing.List[typing.Any]]:
        """Runs the automagic over the configurable"""
        return []

    # TODO: requirement_type can be made typing.Union[typing.Type[T], typing.Tuple[typing.Type[T], ...]]
    #       once mypy properly supports Tuples in instance

    def find_requirements(self,
                          context: interfaces.context.ContextInterface,
                          config_path: str,
                          requirement_root: interfaces.configuration.RequirementInterface,
                          requirement_type: typing.Union[typing.Tuple[typing.Type[R], ...], typing.Type[R]],
                          shortcut: bool = True) \
            -> typing.List[typing.Tuple[str, str, R]]:
        """Determines if there is actually an unfulfilled requirement waiting

        This ensures we do not carry out an expensive search when there is no requirement for a particular requirement

        Args:
            context: Context on which to operate
            config_path: Configuration path of the top-level requirement
            requirement_root: Top-level requirement whose subrequirements will all be searched
            requirement_type: Type of requirement to find
            shortcut: Only returns requirements that live under unsatisfied requirements

        Returns:
            A list of tuples containing the config_path, sub_config_path and requirement identifying the SymbolRequirements
        """
        sub_config_path = interfaces_configuration.path_join(config_path, requirement_root.name)
        results = []  # type: typing.List[typing.Tuple[str, str, R]]
        recurse = not shortcut
        if isinstance(requirement_root, requirement_type):
            if recurse or requirement_root.unsatisfied(context, config_path):
                results.append((config_path, sub_config_path, requirement_root))
        else:
            recurse = True
        if recurse:
            for subreq in requirement_root.requirements.values():
                results += self.find_requirements(context, sub_config_path, subreq, requirement_type, shortcut)
        return results


class StackerLayerInterface(validity.ValidityRoutines, metaclass = ABCMeta):
    """Class that takes a lower layer and attempts to build on it

       stack_order determines the order (from low to high) that stacking layers
       should be attempted lower levels should have lower stack_orders
    """

    stack_order = 0

    @classmethod
    def stack(self,
              context: interfaces.context.ContextInterface,
              layer_name: str,
              progress_callback: validity.ProgressCallback = None) \
            -> typing.Optional[interfaces.layers.DataLayerInterface]:
        """
        Method to determine whether this builder can operate on the named layer.  If so, modify the context appropriately.

        Returns the name of any new_layer stacked on top of this layer or None.  The stacking is therefore strictly
        linear rather than tree driven.

        Configuration options provided by the context are ignored, and defaults are to be used by this method
        to build a space where possible.

        Args:
           context: Context in which to construct the higher layer
           layer_name: Name of the layer to stack on top of
           progress_callback: A callback function to indicate progress through a scan (if one is necessary)
        """
