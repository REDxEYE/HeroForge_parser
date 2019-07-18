import math
import numpy as np
from pathlib import Path

from .ByteIO import ByteIO, split


class HeroGeomerty:
    def __init__(self):
        self.index = []
        self.positions = []
        self.normals = []
        self.uv = []
        self.uv2 = []
        self.vertex_colors = {}
        self.shape_key_data = {}
        self.skin_indices = np.array([])  # type:np.ndarray
        self.additional_skin_indices = np.array([])  # type:np.ndarray
        self.skin_weights = np.array([])  # type:np.ndarray
        self.additional_skin_weights = np.array([])  # type:np.ndarray
        self.original_indices = []
        self.main_skeleton = False
        self.has_geometry = False
        self.skinned = False
        self.bounds = []
        self.scale = []
        self.offset = []


class HeroFile:
    me = (2 ** 8) - 1
    ge = (2 ** 16) - 1

    def __init__(self, path):
        self.reader = ByteIO(path=path)
        self.name = Path(path).name
        self.version = 0
        self.i32_count = 0
        self.i16_count = 0
        self.i8_count = 0
        self.i1_count = 0
        self.export_time = 0

        self.i32_offset = 0
        self.i16_offset = 0
        self.i8_offset = 0
        self.i1_offset = 0
        self.bit_cursor = 0

        self._i1_array = []

        self.options = {}
        self.geometry = HeroGeomerty()
        self.vertex_count = 0

    def read_float(self, offset=0):
        self.reader.seek(self.i32_offset + offset)
        ret = self.reader.read_float()
        self.i32_offset += 4
        return ret

    def read_uint32(self, offset=0):
        self.reader.seek(self.i32_offset + offset)
        val = self.read_float()
        ret = round(val)
        return ret

    def read_uint16(self, offset=0, increment=True):
        self.reader.seek(self.i16_offset + offset)
        ret = self.reader.read_uint16()
        if increment:
            self.i16_offset += 2
        return ret

    def read_int8(self, offset=0):
        self.reader.seek(self.i8_offset + offset)
        ret = self.reader.read_uint8()
        self.i8_offset += 1
        return ret

    def read_string(self, offset=0):
        self.reader.seek(self.i8_offset + offset)
        l = self.read_int8()
        ret = self.reader.read_ascii_string(l)
        self.i8_offset += len(ret)
        return ret

    def read_bit(self):
        bit = self._i1_array[self.bit_cursor]
        self.bit_cursor += 1
        return bit

    def read(self):
        reader = self.reader
        self.version = round(reader.read_float(), 2)
        self.get_start_points()
        with reader.save_current_pos():
            reader.seek(self.i1_offset)
            for _ in range(math.ceil(self.i1_count / 8)):
                byte = reader.read_int8()
                for i in range(8):
                    self._i1_array.append(bool(byte & (1 << i)))
        self._init_settings()
        self._init_indices()
        self._init_points()
        self._init_normals()
        self._init_uvs()
        self._init_vertex_colors()
        self._init_blends()
        self._init_weights()
        self._init_parent()

    def get_bit(self):
        self.bit_cursor += 1
        return self._i1_array[self.bit_cursor - 1]

    def get_start_points(self):
        reader = self.reader
        self.i32_count = reader.read_float_int32()
        self.i16_count = reader.read_float_int32()
        self.i8_count = reader.read_float_int32()
        self.i1_count = reader.read_float_int32()
        e = 20
        if self.version >= 1.4:
            e += 4
            self.export_time = reader.read_float()
        self.i32_offset = e
        self.i16_offset = self.i32_offset + 4 * self.i32_count
        self.i8_offset = self.i16_offset + 2 * self.i16_count
        self.i1_offset = self.i8_offset + self.i8_count

    def _init_settings(self):
        default_attributes = ["mesh", "normals", "uv1", "uv2", "blendTargets", "blendNormals", "weights", "animations",
                              "jointScales", "addon", "paintMapping", "singleParent", "frameMappings", "indices32bit",
                              "originalIndices", "vertexColors"]
        if self.version >= 1.2:
            default_attributes.append('posGroups')
        t = 32
        if self.version >= 1.25:
            default_attributes.append('uvSeams')
            default_attributes.append('rivets')
            t -= 2
        r = {}
        for attr in default_attributes:
            r[attr] = self.get_bit()
        if self.version >= 1.2:
            self.bit_cursor += t
            self.options = r
            self.geometry.main_skeleton = not self.options['addon'] and self.options['weights']

    def _init_indices(self):
        if self.options['mesh']:
            indices_count = self.read_uint32()
            if self.options['indices32bit']:
                self.geometry.index = [self.read_uint32() for _ in range(indices_count)]
            else:
                self.geometry.index = [self.read_uint16() for _ in range(indices_count)]
            if self.options['originalIndices']:
                if self.options['indices32bit']:
                    self.geometry.original_indices = [self.read_uint32() for _ in range(indices_count)]
                else:
                    self.geometry.original_indices = [self.read_uint16() for _ in range(indices_count)]

    def _init_points(self):
        if self.options['mesh']:
            vertex_count = self.read_uint32() if self.options['indices32bit'] else self.read_uint16()
            self.vertex_count = vertex_count
            self.geometry.has_geometry = True
            # Z Y X
            bbox = [self.read_float() for _ in range(6)]
            scale = [bbox[3] - bbox[0], bbox[4] - bbox[1], (bbox[5] - bbox[2])]
            self.geometry.offset = [bbox[0] * scale[0], bbox[1] * scale[1], bbox[2] * scale[2]]
            self.geometry.bounds = [bbox[0:3], bbox[3:6]]
            verts = []
            for _ in range(vertex_count):
                verts.append((self.read_uint16() / self.ge * scale[0] + bbox[0],
                              self.read_uint16() / self.ge * scale[1] + bbox[1],
                              self.read_uint16() / self.ge * scale[2] + bbox[2]
                              ))
                self.geometry.positions = verts

    def _init_normals(self):
        if self.options['normals']:
            if self.vertex_count != 0:
                normals = []
                r = 0
                for _ in range(self.vertex_count):
                    normals.append(self.read_int8() / self.me * 2 - 1)
                    normals.append(self.read_int8() / self.me * 2 - 1)
                    normals.append(
                        (2 * self.get_bit() - 1) * (1 - math.pow(normals[r], 2) - math.pow(normals[r + 1], 2)))
                    r += 3
                self.geometry.normals = split(normals, 3)

    def _init_uvs(self):
        if self.options['uv1']:
            uvs = ['uv', 'uv2'] if self.options['uv2'] else ['uv']
            for uv in uvs:
                n = [self.read_float() for _ in range(4)]
                s = [n[2] - n[0], n[3] - n[1]]
                u = []
                for i in range(self.vertex_count):
                    u.append((self.read_uint16() / self.ge * s[0] + n[0], self.read_uint16() / self.ge * s[1] + n[1]))
                setattr(self.geometry, uv, u)

    def _init_vertex_colors(self):
        if self.options['vertexColors']:
            layer_count = self.read_int8()
            for t in range(layer_count):
                layer_name = self.read_string()
                v_colors = []
                for _ in range(self.vertex_count):
                    col = self.read_int8()
                    v_colors.append(col / 255)
                    v_colors.append(col / 255)
                    v_colors.append(col / 255)
                self.geometry.vertex_colors[layer_name] = v_colors

    def _init_blends(self):
        if self.options['blendTargets']:
            shape_key_count = self.read_int8()
            if shape_key_count:
                shape_key_data = {}
                for shape_key_id in range(shape_key_count):
                    shape_key_name = self.read_string()
                    o = [self.read_float() for _ in range(6)]
                    u = [o[3] - o[0], o[4] - o[1], o[5] - o[2]]
                    c = []
                    for d in range(self.vertex_count):
                        c.append(self.read_int8() / self.me * u[0] + o[0])
                        c.append(self.read_int8() / self.me * u[1] + o[1])
                        c.append(self.read_int8() / self.me * u[2] + o[2])
                    shape_key_data[shape_key_name] = split(c, 3)
                    if self.options['blendNormals']:
                        for _ in range(self.vertex_count):
                            self.read_int8()
                            self.read_int8()
                            self.get_bit()
                self.geometry.shape_key_data = shape_key_data

    def _init_weights(self):
        if self.options['weights']:
            self.geometry.skinned = True
            weight_per_vert = self.read_int8()
            additional_weights = max(0, weight_per_vert - 4)
            skin_indices = np.zeros(4 * self.vertex_count, dtype=np.int16)
            additional_skin_indices = np.zeros(additional_weights * self.vertex_count, dtype=np.int16)
            u = 4 if weight_per_vert < 4 else weight_per_vert
            for l in range(u):
                if weight_per_vert > l:
                    if l < 4:
                        for t in range(self.vertex_count):
                            skin_indices[4 * t + l] = self.read_uint16(2 * (t * weight_per_vert + l), False)
                    else:
                        for t in range(self.vertex_count):
                            additional_skin_indices[t * additional_weights + (l - 4)] = self.read_uint16(
                                2 * (t * additional_weights + l), False)
            self.geometry.skin_indices = skin_indices.reshape((-1,weight_per_vert,))
            self.geometry.additional_skin_indices = additional_skin_indices.reshape((-1,weight_per_vert,))
            self.i16_offset = self.i16_offset + weight_per_vert * self.vertex_count * 2;
            skin_weights = np.zeros(4 * self.vertex_count, dtype=np.float32)
            additional_skin_weights = np.zeros(additional_weights * self.vertex_count, dtype=np.float32)
            u = 4 if weight_per_vert < 4 else weight_per_vert
            for f in range(u):
                if weight_per_vert > f:
                    if f < 4:
                        for c in range(self.vertex_count):
                            skin_weights[4 * c + f] = self.read_uint16(2 * (c * weight_per_vert + f), False) / self.ge
                    else:
                        for c in range(self.vertex_count):
                            additional_skin_weights[c * additional_weights + (f - 4)] = self.read_uint16(
                                2 * (c * weight_per_vert + f), False) / self.ge
            self.geometry.skin_weights = skin_weights.reshape((-1,weight_per_vert))
            self.geometry.additional_skin_weights = additional_skin_weights.reshape((-1,weight_per_vert))
            self.i16_offset = self.i16_offset + weight_per_vert * self.vertex_count * 2

    def _init_parent(self):
        if self.options['singleParent']:
            name = self.read_string()
            e = self.read_uint16()
            r = np.zeros(4 * self.vertex_count)
            i = np.zeros(4 * self.vertex_count)
            a = 4 * self.vertex_count
            for n in range(a):
                r[n] = e if n % 4 == 0 else 0
                i[n] = 1 if n % 4 == 0 else 0

            self.geometry.skin_indices = r.reshape((-1,4))
            self.geometry.skin_weights = i.reshape((-1,4))


if __name__ == '__main__':
    a = HeroFile('hf_bodyUpper_loRez_dragon.ckb')
    a.read()
    print(a)
