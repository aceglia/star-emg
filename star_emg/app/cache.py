import os
import json


class Cache:
    """
    This class provides a simple caching mechanism using a JSON file. It allows you to store key-value pairs in a cache file and retrieve them later. The cache is initialized when the class is instantiated, and it can be removed if needed.
    Parameters
    ----------
    cache_file : str
        The path to the cache file. If the file does not exist, it will be created when the first value is set to the cache.
    Methods
    -------
    remove_cache()
        Removes the cache file.
    set_to_cache(key, value)
        Sets a key-value pair to the cache and saves it to the cache file.
    load_from_cache()
        Loads the cache from the cache file.
    get_from_cache(key)
        Retrieves the value associated with the given key from the cache. If the cache is not initialized or the key does not exist, it returns None.

    """

    def __init__(self, cache_file):
        self.cache_file = cache_file
        self.cache_dict = {}
        self.cache_initialized = False
        if os.path.exists(self.cache_file):
            self.load_from_cache()

    def remove_cache(self):
        os.remove(self.cache_file)

    def set_to_cache(self, key, value):
        self.cache_dict[key] = value
        with open(self.cache_file, "w") as f:
            json.dump(self.cache_dict, f)
        self.cache_initialized = True

    def load_from_cache(self):
        with open(self.cache_file, "r") as f:
            self.cache_dict = json.load(f)
        self.cache_initialized = True

    def get_from_cache(self, key):
        if not self.cache_initialized:
            return None
        return self.cache_dict.get(key, None)
