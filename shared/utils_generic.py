

def todict(obj, classkey=None):
    if isinstance(obj, dict):
        data = {}
        for (k, v) in obj.items():
            data[k] = todict(v, classkey)
        return data
    elif hasattr(obj, "_ast"):
        return todict(obj._ast())
    elif hasattr(obj, "__iter__") and not isinstance(obj, str):
        return [todict(v, classkey) for v in obj]
    elif hasattr(obj, "__dict__"):
        data = dict([(key, todict(value, classkey))
            for key, value in obj.__dict__.items()
            if not callable(value) and not key.startswith('_')])
        if classkey is not None and hasattr(obj, "__class__"):
            data[classkey] = obj.__class__.__name__
        return data
    else:
        return obj


def remove_null_values(dictionary):
  """Recursively removes keys with null values from a dictionary and its nested dictionaries.

  Args:
    dictionary: The dictionary to modify.

  Returns:
    A new dictionary with null values removed.
  """

  result = {}
  for key, value in dictionary.items():
    if isinstance(value, dict):
      result[key] = remove_null_values(value)
    elif value is not None:
      result[key] = value
  return result


def get_element_by_attribute(client, collection_name, attribute, value):
  """
  Retrieves an element from a MongoDB collection based on an attribute-value pair.

  Args:
      client (MongoClient): A MongoClient object connected to the MongoDB database.
      collection_name (str): The name of the collection to search.
      attribute (str): The name of the attribute to search by.
      value: The value to match in the specified attribute.

  Returns:
      dict: The document matching the attribute-value pair, or None if not found.
  """

  collection = client[collection_name]
  filter = {attribute: value}

  try:
    # Find one document that matches the filter
    document = collection.find_one(filter)
    return document
  except Exception as e:
    print(f"Error retrieving element: {e}")
    return None
