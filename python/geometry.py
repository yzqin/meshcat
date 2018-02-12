import base64
import uuid

import umsgpack
import numpy as np


class SceneElement:
    def __init__(self):
        self.uuid = str(uuid.uuid1())


class ReferenceSceneElement(SceneElement):
    def serialize_in_object(self, object_data):
        object_data.setdefault(self.field, []).append(self.serialize(object_data))
        return self.uuid


class Geometry(ReferenceSceneElement):
    field = "geometries"


class Material(ReferenceSceneElement):
    field = "materials"


class Texture(ReferenceSceneElement):
    field = "textures"


class Image(ReferenceSceneElement):
    field = "images"


class Box(Geometry):
    def __init__(self, lengths):
        super().__init__()
        self.lengths = lengths

    def serialize(self, object_data):
        return {
            "uuid": self.uuid,
            "type": "BoxGeometry",
            "width": self.lengths[0],
            "height": self.lengths[1],
            "depth": self.lengths[2]
        }


class MeshMaterial(Material):
    def __init__(self, color=0xffffff, reflectivity=0.5, map=None, **kwargs):
        super().__init__()
        self.color = color
        self.reflectivity = reflectivity
        self.map = map
        self.properties = kwargs

    def serialize(self, object_data):
        data = {
            "uuid": self.uuid,
            "type": self._type,
            "color": self.color,
            "reflectivity": self.reflectivity,
        }
        data.update(self.properties)
        if self.map is not None:
            data["map"] = self.map.serialize_in_object(object_data)
        return data


class MeshBasicMaterial(MeshMaterial):
    _type="MeshBasicMaterial"


class MeshPhongMaterial(MeshMaterial):
    _type="MeshPhongMaterial"


class MeshLambertMaterial(MeshMaterial):
    _type="MeshLambertMaterial"


class MeshToonMaterial(MeshMaterial):
    _type="MeshToonMaterial"


class PngImage(Image):
    def __init__(self, data):
        super().__init__()
        self.data = data

    @staticmethod
    def from_file(fname):
        with open(fname, "rb") as f:
            return PngImage(f.read())

    def serialize(self, object_data):
        return {
            "uuid": self.uuid,
            "url": "data:image/png;base64," + base64.b64encode(self.data).decode('ascii')
        }


class GenericTexture(Texture):
    def __init__(self, properties):
        super().__init__()
        self.properties = properties

    def serialize(self, object_data):
        data = {"uuid": self.uuid}
        data.update(self.properties)
        if "image" in data:
            image = data["image"]
            data["image"] = image.serialize_in_object(object_data)
        return data


class ImageTexture(Texture):
    def __init__(self, image, wrap=[1001, 1001], repeat=[1, 1], **kwargs):
        super().__init__()
        self.image = image
        self.wrap = wrap
        self.repeat = repeat
        self.properties = kwargs

    def serialize(self, object_data):
        data = {
            "uuid": self.uuid,
            "wrap": self.wrap,
            "repeat": self.repeat,
            "image": self.image.serialize_in_object(object_data)
        }
        data.update(self.properties)
        return data


class GenericMaterial(Material):
    def __init__(self, properties):
        self.properties = properties
        self.uuid = str(uuid.uuid1())

    def serialize(self, object_data):
        data = {"uuid": self.uuid}
        data.update(self.properties)
        if "map" in data:
            texture = data["map"]
            data["map"] = texture.serialize_in_object(object_data)
        return data


class Object(SceneElement):
    def __init__(self, geometry, material):
        super().__init__()
        self.geometry = geometry
        self.material = material

    def serialize(self):
        data = {
            "metadata": {
                "version": 4.5,
                "type": "Object",
            },
            "geometries": [],
            "materials": [],
            "object": {
                "uuid": self.uuid,
                "type": self._type,
                "geometry": self.geometry.uuid,
                "material": self.material.uuid
            }
        }
        self.geometry.serialize_in_object(data)
        self.material.serialize_in_object(data)
        return data


class Mesh(Object):
    _type = "Mesh"


def item_size(array):
    if array.ndim == 1:
        return 1
    elif array.ndim == 2:
        return array.shape[0]
    else:
        raise ValueError("I can only pack 1- or 2-dimensional numpy arrays, but this one has {:d} dimensions".format(array.ndim))


def threejs_type(dtype):
    if dtype == np.uint8:
        return "Uint8Array", 0x12
    elif dtype == np.int32:
        return "Int32Array", 0x15
    elif dtype == np.uint32:
        return "Uint32Array", 0x16
    elif dtype == np.float32:
        return "Float32Array", 0x17
    else:
        raise ValueError("Unsupported datatype: " + str(dtype))


def pack_numpy_array(x):
    typename, extcode = threejs_type(x.dtype)
    return {
        "itemSize": item_size(x),
        "type": typename,
        "array": umsgpack.Ext(extcode, x.tobytes()),
        "normalized": False
    }


class ObjMeshGeometry(Geometry):
    def __init__(self, contents):
        super().__init__()
        self.contents = contents

    def serialize(self, object_data):
        return {
            "type": "_meshfile",
            "uuid": self.uuid,
            "format": "obj",
            "data": self.contents
        }

    @staticmethod
    def from_file(fname):
        with open(fname, "r") as f:
            return ObjMeshGeometry(f.read())


class PointsGeometry(Geometry):
    def __init__(self, points, color=None):
        super().__init__()
        self.points = points
        self.color = color

    def serialize(self, object_data):
        attrs = {"position": pack_numpy_array(self.points)}
        if self.color is not None:
            attrs["color"] = pack_numpy_array(self.color)
        return {
            "uuid": self.uuid,
            "type": "BufferGeometry",
            "data": {
                "attributes": attrs
            }
        }


class PointsMaterial(Material):
    def __init__(self, size=0.001, color=0xffffff):
        super().__init__()
        self.size = size
        self.color = color

    def serialize(self, object_data):
        return {
            "uuid": self.uuid,
            "type": "PointsMaterial",
            "color": self.color,
            "size": self.size,
            "vertexColors": 2
        }


class Points(Object):
    _type = "Points"


class SetObject:
    def __init__(self, object, path=[]):
        self.object = object
        self.path = path

    def serialize(self):
        return {
            "type": "set_object",
            "object": self.object.serialize(),
            "path": self.path
        }


class SetTransform:
    def __init__(self, position, quaternion, path=[]):
        self.position = position
        self.quaternion = quaternion
        self.path = path

    def serialize(self):
        return {
            "type": "set_transform",
            "path": self.path,
            "position": self.position,
            "quaternion": self.quaternion
        }



class ViewerMessage:
    def __init__(self, commands):
        self.commands = commands

    def serialize(self):
        return {
            "commands": [c.serialize() for c in self.commands]
        }

    def pack(self):
        return umsgpack.packb(self.serialize())
