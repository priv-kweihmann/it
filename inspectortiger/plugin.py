import importlib
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

import inspectortiger.inspector
from inspectortiger.utils import _PSEUDO_FIELDS, logger


class PluginLoadError(ImportError):
    pass


class _Plugin(type):
    _plugins = {}

    def __call__(
        cls,
        plugin,
        namespace,
        inactive=False,
        static_name=None,
        python_version=(),
    ):
        namespace = cls.expand(namespace)
        args = tuple(
            (k, v) for k, v in locals().items() if k not in _PSEUDO_FIELDS
        )
        if args not in cls._plugins:
            cls._plugins[args] = super().__call__(**dict(args))
        return cls._plugins[args]


@dataclass(unsafe_hash=True)
class Plugin(metaclass=_Plugin):
    plugin: str
    namespace: str
    inactive: bool = False
    static_name: Optional[str] = None
    python_version: Tuple[int, ...] = ()

    @classmethod
    def from_simple(cls, simple):
        try:
            namespace, plugin = simple.rsplit(".", 1)
        except ValueError:
            namespace, *plugin = simple

        plugin = "".join(plugin)
        return cls(plugin, namespace)

    @classmethod
    def from_config(cls, config):
        result = []
        for namespace, plugins in config.items():
            result.extend(
                cls.from_simple(f"{namespace}.{plugin}") for plugin in plugins
            )
        return result

    @classmethod
    def require(cls, plugin, namespace=None):
        def wrapper(func):
            if namespace is None:
                requirement = cls.from_simple(plugin)
            else:
                requirement = cls(plugin, namespace)

            if not hasattr(func, "requires"):
                func.requires = []
            func.requires.append(requirement)
            return func

        return wrapper

    def __post_init__(self):

        namespace = self.expand(self.namespace)
        self.namespace = namespace

        if self.static_name is None:
            self.static_name = f"{namespace}.{self.plugin}"

    def __str__(self):
        return self.plugin

    def load(self):
        with inspectortiger.inspector.Inspector.buffer():
            try:
                plugin = importlib.import_module(self.static_name)
            except ImportError:
                raise PluginLoadError(
                    f"Couldn't load '{self.plugin}' from `{self.namespace}` namespace!"
                )

            if hasattr(plugin, "__py_version__"):
                self.python_version = plugin.__py_version__

            if self.python_version > sys.version_info:
                self.inactive = True
                logger.debug(
                    f"`{self.plugin}` plugin from `{self.namespace}` couldn't load because of incompatible version."
                )
                raise inspectortiger.inspector.BufferExit

        for actionable in dir(plugin):
            actionable = getattr(plugin, actionable)
            if hasattr(
                actionable, "_inspection_mark"
            ):  # TODO: ismarked(callable)
                actionable.plugin = self

    @staticmethod
    def expand(namespace):
        # prefixes
        # @ => inspectortiger.plugins
        # ? => local plugin

        if namespace == "@":
            return "inspectortiger.plugins"
        elif namespace.startswith("@"):
            return namespace.replace("@", "inspectortiger.plugins.")
        elif namespace == "?":
            return ""
        else:
            return namespace
