import math

from pathlib import Path

from .ByteIO import ByteIO


class HeroGeomerty:
    def __init__(self):
        self.index = []
        self.positions = []
        self.normals = []
        self.uv = []
        self.uv2 = []
        self.original_indices = []
        self.main_skeleton = False
        self.has_geometry = False
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

    def read_float(self):
        with self.reader.save_current_pos():
            self.reader.seek(self.i32_offset)
            ret = self.reader.read_float()
            self.i32_offset += 4
        return ret

    def read_uint32(self):
        with self.reader.save_current_pos():
            self.reader.seek(self.i32_offset)
            val = self.read_float()
            ret = round(val)
            self.i32_offset += 4
        return ret

    def read_uint16(self):
        with self.reader.save_current_pos():
            self.reader.seek(self.i16_offset)
            ret = self.reader.read_uint16()
            self.i16_offset += 2
        return ret

    def read_uint8(self):
        with self.reader.save_current_pos():
            self.reader.seek(self.i8_offset)
            ret = self.reader.read_uint8()
            self.i8_offset += 1
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
        t = 32
        if self.version >= 1.2:
            default_attributes.append('posGroups')
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
            t = [self.read_float() for _ in range(6)]
            i = [t[3] - t[0], t[4] - t[1], (t[5] - t[2])]
            tmp =                   [t[5] * i[2], t[3] * i[0], t[4] * i[1]]
            self.geometry.offset =  [t[2] * i[2], t[0] * i[0], t[1] * i[1]]
            self.geometry.bounds = [t[0:3], t[3:6]]
            # self.geometry.scale = [i[2], i[0]*0.5, i[1]*0.5]
            self.geometry.scale = [i[2], i[0], i[1]]
            print('{:50} SCALE X:{:10.5} Y:{:10.5} Z:{:10.5}  OFFSET  X:{:10.5} Y:{:10.5} Z:{:10.5} ||||| X:{:10.5} Y:{:10.5} Z:{:10.5}'.format(self.name, *self.geometry.scale, *self.geometry.offset,*tmp))
            verts = []
            for _ in range(vertex_count):
                verts.append((self.read_uint16() / self.ge,  # * (i[2]),
                              self.read_uint16() / self.ge,  # * (i[0] * 0.5),
                              self.read_uint16() / self.ge,  # * (i[1])
                              ))
                self.geometry.positions = verts

    def _init_normals(self):
        if self.options['normals']:
            if self.vertex_count != 0:
                normals = []
                r = 0
                for _ in range(self.vertex_count):
                    normals.append(self.read_uint8() / self.me * 2 - 1)
                    normals.append(self.read_uint8() / self.me * 2 - 1)
                    normals.append((2 * self.get_bit() - 1) * (1 - normals[r] ** 2 - normals[r + 1] ** 2))
                    r += 3
                self.geometry.normals = normals

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


if __name__ == '__main__':
    a = HeroFile('hf_bodyUpper_loRez_dragon.ckb')
    a.read()
    print(a)
