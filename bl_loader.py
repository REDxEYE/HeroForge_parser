import random
from pathlib import Path
from typing import Dict

from .HeroForge import HeroBone
from . import HeroForge

import bpy
from mathutils import *

from .ByteIO import split


class HeroIO:
    def __init__(self, path: str = ''):
        self.path = Path(path)
        self.name = self.path.stem
        self.hero = HeroForge.HeroFile(path)
        self.hero.read()

        self.armature_obj = None
        self.armature = None

        # just a temp containers
        self.mesh_obj = None
        self.mesh_data = None

        self.create_models()
        # bpy.ops.object.mode_set(mode='OBJECT')

    def create_skeleton(self, ):

        bpy.ops.object.armature_add(enter_editmode=True)
        #
        self.armature_obj = bpy.context.object
        self.armature_obj.show_x_ray = True
        self.armature_obj.name = self.name + '_ARM'
        # rotation_mode
        self.armature = self.armature_obj.data
        self.armature.name = self.name + "_ARM_DATA"
        try:
            self.armature.edit_bones.remove(self.armature.edit_bones[0])
        except:
            pass
        bpy.ops.object.mode_set(mode='EDIT')
        bones = []
        for se_bone in self.hero.geometry.bones:
            bones.append((self.armature.edit_bones.new(str(se_bone.name)), se_bone))
        #
        for bl_bone, se_bone in bones:  # type: bpy.types.EditBone,HeroBone
            if se_bone.parent_id != -1:
                bl_parent, parent = bones[se_bone.parent_id]
                bl_bone.parent = bl_parent
            else:
                pass
            bl_bone.tail = Vector([0, 0, 1]) + bl_bone.head

        bpy.ops.object.mode_set(mode='POSE')
        for se_bone in self.hero.geometry.bones:  # type:HeroBone
            bl_bone = self.armature_obj.pose.bones.get(str(se_bone.name))
            # mat = Matrix(fix_matrix(se_bone['matrix']))
            mat_loc = Matrix.Translation(se_bone.pos)
            mat_sca = Matrix.Scale(1, 4, se_bone.scale)
            eul = Quaternion(se_bone.quat).to_euler()
            eul.order = 'ZYX'
            mat_rot = eul.to_matrix().to_4x4()
            mat_out = mat_loc * mat_rot * mat_sca
            bl_bone.matrix_basis.identity()
            if bl_bone.parent:
                bl_bone.matrix = mat_out
            else:
                bl_bone.matrix = mat_out
        bpy.ops.pose.armature_apply()
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='OBJECT')

    @staticmethod
    def get_material(mat_name, model_ob):
        if mat_name:
            mat_name = mat_name
        else:
            mat_name = "Material"
        mat_ind = 0
        md = model_ob.data
        mat = None
        for candidate in bpy.data.materials:  # Do we have this material already?
            if candidate.name == mat_name:
                mat = candidate
        if mat:
            if md.materials.get(mat.name):  # Look for it on this mesh_data
                for i in range(len(md.materials)):
                    if md.materials[i].name == mat.name:
                        mat_ind = i
                        break
            else:  # material exists, but not on this mesh_data
                md.materials.append(mat)
                mat_ind = len(md.materials) - 1
        else:  # material does not exist
            mat = bpy.data.materials.new(mat_name)
            md.materials.append(mat)
            # Give it a random colour
            rand_col = []
            for i in range(3):
                rand_col.append(random.uniform(.4, 1))
            mat.diffuse_color = rand_col

            mat_ind = len(md.materials) - 1

        return mat_ind

    def build_meshes(self):
        mesh_obj = bpy.data.objects.new(self.hero.name, bpy.data.meshes.new(self.hero.name + '_MESH'))
        bpy.context.scene.objects.link(mesh_obj)
        mesh = mesh_obj.data
        if self.armature_obj:
            mesh_obj.parent = self.armature_obj

            modifier = mesh_obj.modifiers.new(type="ARMATURE", name="Armature")
            modifier.object = self.armature_obj

        # bones = [bone_list[i] for i in remap_list]

        if len(self.hero.geometry.skin_indices):
            indices = set(self.hero.geometry.skin_indices.reshape((-1,)))
            # print(indices)
            weight_groups = {str(bone): mesh_obj.vertex_groups.new(str(bone)) for bone in
                             indices}
        uvs = self.hero.geometry.uv
        print('Building mesh:', self.hero.name)
        mesh.from_pydata(self.hero.geometry.positions, [], split(self.hero.geometry.index))
        mesh.update()
        # mesh_obj.scale = self.hero.geometry.scale
        # mesh_obj.location = self.hero.geometry.offset
        mesh.uv_textures.new()
        uv_data = mesh.uv_layers[0].data
        for i in range(len(uv_data)):
            u = uvs[mesh.loops[i].vertex_index]
            uv_data[i].uv = u
        if len(self.hero.geometry.skin_indices):
            for n, (bones, weights) in enumerate(zip(self.hero.geometry.skin_indices, self.hero.geometry.skin_weights)):
                for bone, weight in zip(bones, weights):
                    if weight != 0:
                        # if bone in mesh_data['bone_map']:
                        bone_name = str(bone)  # ['name']
                        weight_groups[bone_name].add([n], weight, 'REPLACE')
        self.get_material('WHITE', mesh_obj)
        bpy.ops.object.select_all(action="DESELECT")
        mesh_obj.select = True
        bpy.context.scene.objects.active = mesh_obj
        bpy.ops.object.shade_smooth()
        mesh.normals_split_custom_set_from_vertices(self.hero.geometry.normals)
        # mesh.normals_split_custom_set(normals)
        mesh.use_auto_smooth = True
        self.mesh_data = mesh
        self.mesh_obj = mesh_obj

        if self.hero.geometry.vertex_colors:
            bpy.ops.object.select_all(action="DESELECT")
            for layer, v_color in self.hero.geometry.vertex_colors.items():
                self.mesh_obj.select = True
                bpy.context.scene.objects.active = self.mesh_obj
                bpy.ops.object.mode_set(mode='VERTEX_PAINT')
                if layer not in  self.mesh_data.vertex_colors:
                    self.mesh_data.vertex_colors.new(name=layer)
                color_layer = self.mesh_data.vertex_colors[layer].data
                for i in range(len(color_layer)):
                    u = v_color[self.mesh_data.loops[i].vertex_index]
                    color_layer[i].color = u

            bpy.ops.object.mode_set(mode='OBJECT')

    def create_models(self):
        if self.hero.geometry.main_skeleton:
            self.create_skeleton()
        else:
            self.armature = None
            self.armature_obj = None
        self.build_meshes()
        self.add_flexes()

    def add_flexes(self):
        # Creating base shape key
        self.mesh_obj.shape_key_add(name='base')
        for flex_name, flex_data in self.hero.geometry.shape_key_data.items():
            # if blender mesh_data does not have FLEX_NAME - create it,
            # otherwise work with existing
            if not self.mesh_obj.data.shape_keys.key_blocks.get(flex_name):
                self.mesh_obj.shape_key_add(name=flex_name)

            for vertex_index, flex_vert in enumerate(flex_data):
                vx = self.mesh_obj.data.vertices[vertex_index].co.x
                vy = self.mesh_obj.data.vertices[vertex_index].co.y
                vz = self.mesh_obj.data.vertices[vertex_index].co.z
                fx, fy, fz = flex_vert
                self.mesh_obj.data.shape_keys.key_blocks[flex_name].data[vertex_index].co = (
                    fx + vx, fy + vy, fz + vz)
