
import pkgutil
import upstox_client
print(f"Path: {upstox_client.__path__}")
try:
    for importer, modname, ispkg in pkgutil.walk_packages(upstox_client.__path__, upstox_client.__name__ + "."):
        if "market" in modname or "feeder" in modname:
            print(modname)
except Exception as e:
    print(e)
