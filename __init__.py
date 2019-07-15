import bpy
from pathlib import Path

bl_info = {
    "name": "HeroForge model import",
    "author": "RED_EYE",
    "version": (0, 1),
    "blender": (2, 79, 0),
    "location": "File > Import-Export > HeroForge model (.ckb)",
    "description": "Addon allows to import HeroForge models",
    "category": "Import-Export"
}

from bpy.props import StringProperty, BoolProperty, CollectionProperty


class HeroForge_OT_operator(bpy.types.Operator):
    """Load HeroForge ckb models"""
    bl_idname = "import_mesh.ckb"
    bl_label = "Import HeroForge model"
    bl_options = {'UNDO'}

    filepath = StringProperty(
        subtype='FILE_PATH',
    )
    files = CollectionProperty(name='File paths', type=bpy.types.OperatorFileListElement)
    filter_glob = StringProperty(default="*.ckb", options={'HIDDEN'})

    def execute(self, context):
        from . import bl_loader
        directory = Path(self.filepath).parent.absolute()
        for file in self.files:
            importer = bl_loader.HeroIO(str(directory / file.name))

        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}


def menu_import(self, context):
    self.layout.operator(HeroForge_OT_operator.bl_idname, text="HeroForge model (.ckb)")


def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_import.append(menu_import)


def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_import.remove(menu_import)


if __name__ == "__main__":
    register()
