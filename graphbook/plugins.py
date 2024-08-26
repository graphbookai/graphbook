import importlib
import traceback
import os.path as osp


def setup_plugins(plugin_modules, web_dest):
    if web_dest == None:
        web_dest = osp.join(__file__, "../web/src")
    def get_plugin_steps(plugin):
        try:
            return plugin.get_steps()
        except NotImplementedError:
            print(
                f"Plugin {plugin} does not have a get_steps method which must be implemented. Ignoring any steps from this plugin."
            )
        except Exception:
            traceback.print_exc()
            return {}

    def get_plugin_resources(plugin):
        try:
            return plugin.get_resources()
        except NotImplementedError:
            print(
                f"Plugin {plugin} does not have a get_resources method which must be implemented. Ignoring any resources from this plugin."
            )
        except Exception:
            traceback.print_exc()
            return {}

    def get_plugin_web(plugin):
        if not hasattr(plugin, "get_web"):
            return {}
        try:
            return plugin.get_web()
        except Exception:
            traceback.print_exc()
            return {}

    plugins = [importlib.import_module(module) for module in plugin_modules]
    steps = [get_plugin_steps(plugin) for plugin in plugins]
    resources = [get_plugin_resources(plugin) for plugin in plugins]
    web = [get_plugin_web(plugin) for plugin in plugins]
    return steps, resources, web
