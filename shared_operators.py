import math
from pathlib import Path

import bpy
from bpy.props import StringProperty, BoolProperty, CollectionProperty, EnumProperty, FloatProperty

from .source1.content_manager import ContentManager
from .source1.mdl.structs.header import StudioHDRFlags
from .source1.new_model_import import import_model, import_materials
from .source2.resouce_types.valve_model import ValveModel
from .utilities.path_utilities import backwalk_file_resolver


class LoadPlaceholder_OT_operator(bpy.types.Operator):
    bl_idname = "source_io.load_placeholder"
    bl_label = "Load placeholder"
    bl_options = {'UNDO'}

    def execute(self, context):
        content_manager = ContentManager()
        content_manager.deserialize(bpy.context.scene.get('content_manager_data', {}))

        for obj in context.selected_objects:
            print(f'Loading {obj.name}')
            if obj.get("entity_data", None):
                custom_prop_data = obj['entity_data']
                model_type = Path(custom_prop_data['prop_path']).suffix
                collection = bpy.data.collections.get(custom_prop_data['type'],
                                                      None) or bpy.data.collections.new(
                    name=custom_prop_data['type'])
                if model_type in ['.vmdl_c', '.vmdl_c']:
                    mld_file = backwalk_file_resolver(custom_prop_data['parent_path'],
                                                      Path(custom_prop_data['prop_path']).with_suffix('.vmdl_c'))

                    if mld_file:

                        try:
                            bpy.context.scene.collection.children.link(collection)
                        except:
                            pass

                        model = ValveModel(mld_file)
                        model.load_mesh(True, parent_collection=collection,
                                        skin_name=custom_prop_data.get("skin_id", 'default'))
                        for ob in model.objects:  # type:bpy.types.Object
                            ob.location = obj.location
                            ob.rotation_mode = "XYZ"
                            ob.rotation_euler = obj.rotation_euler
                            ob.scale = obj.scale
                        bpy.data.objects.remove(obj)
                    else:
                        self.report({'INFO'}, f"Model '{custom_prop_data['prop_path']}_c' not found!")
                elif model_type == '.mdl':
                    prop_path = Path(custom_prop_data['prop_path'])
                    mld_file = content_manager.find_file(prop_path)
                    if mld_file:
                        vvd_file = content_manager.find_file(prop_path.with_suffix('.vvd'))
                        vtx_file = content_manager.find_file(prop_path.parent / f'{prop_path.stem}.dx90.vtx')
                        model_container = import_model(mld_file, vvd_file, vtx_file, None, False, collection,
                                                       True, True)
                        if model_container.armature:
                            armature = model_container.armature
                            armature.location = obj.location
                            armature.rotation_mode = "XYZ"
                            armature.rotation_euler = obj.rotation_euler
                            armature.rotation_euler[2] += math.radians(90)
                            armature.scale = obj.scale
                        else:
                            for mesh_obj in model_container.objects:
                                mesh_obj.location = obj.location
                                mesh_obj.rotation_mode = "XYZ"
                                mesh_obj.rotation_euler = obj.rotation_euler
                                mesh_obj.scale = obj.scale
                        import_materials(model_container.mdl)
                        skin = custom_prop_data.get('skin', None)
                        if skin:
                            for model in model_container.objects:
                                if str(skin) in model['skin_groups']:
                                    skin = str(skin)
                                    skin_materials = model['skin_groups'][skin]
                                    current_materials = model['skin_groups'][model['active_skin']]
                                    print(skin_materials, current_materials)
                                    for skin_material, current_material in zip(skin_materials, current_materials):
                                        swap_materials(model, skin_material[-63:], current_material[-63:])
                                    model['active_skin'] = skin
                                else:
                                    print(f'Skin {skin} not found')

                        bpy.data.objects.remove(obj)
        return {'FINISHED'}


def swap_materials(obj, new_material_name, target_name):
    mat = bpy.data.materials.get(new_material_name, None) or bpy.data.materials.new(name=new_material_name)
    print(f'Swapping {target_name} with {new_material_name}')
    for n, obj_mat in enumerate(obj.data.materials):
        print(target_name, obj_mat.name)
        if obj_mat.name == target_name:
            print(obj_mat.name, "->", mat.name)
            obj.data.materials[n] = mat
            break


class ChangeSkin_OT_operator(bpy.types.Operator):
    bl_idname = "source_io.select_skin"
    bl_label = "Change skin"
    bl_options = {'UNDO'}

    skin_name: bpy.props.StringProperty(name="skin_name", default="default")

    def execute(self, context):
        obj = context.active_object
        if obj.get('model_type', False):
            model_type = obj['model_type']
            if model_type == 's1':
                self.handle_s1(obj)
            elif model_type == 's2':
                self.handle_s2(obj)
            else:
                self.handle_s2(obj)

        obj['active_skin'] = self.skin_name

        return {'FINISHED'}

    def handle_s1(self, obj):
        skin_materials = obj['skin_groups'][self.skin_name]
        current_materials = obj['skin_groups'][obj['active_skin']]
        for skin_material, current_material in zip(skin_materials, current_materials):
            swap_materials(obj, skin_material[-63:], current_material[-63:])

    def handle_s2(self, obj):
        skin_material = obj['skin_groups'][self.skin_name]
        current_material = obj['skin_groups'][obj['active_skin']]

        mat_name = Path(skin_material).stem
        current_mat_name = Path(current_material).stem
        swap_materials(obj, mat_name, current_mat_name)


class SourceIOUtils_PT_panel(bpy.types.Panel):
    bl_label = "SourceIO utils"
    bl_idname = "source_io.utils"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SourceIO"

    @classmethod
    def poll(cls, context):
        obj = context.active_object  # type:bpy.types.Object
        if obj:
            return obj.type in ["EMPTY", 'MESH']
        else:
            return False

    def draw(self, context):
        self.layout.label(text="SourceIO stuff")
        obj = context.active_object  # type:bpy.types.Object
        if obj.get("entity_data", None):
            entiry_data = obj['entity_data']
            entity_raw_data = entiry_data.get('entity', {})

            box = self.layout.box()
            box.operator('source_io.load_placeholder')
            box = self.layout.box()
            for k, v in entity_raw_data.items():
                row = box.row()
                row.label(text=f'{k}:')
                row.label(text=str(v))

        if obj.get("skin_groups", None):
            self.layout.label(text="Skins")
            box = self.layout.box()
            for skin, _ in obj['skin_groups'].items():
                row = box.row()
                op = row.operator('source_io.select_skin', text=skin)
                op.skin_name = skin
                if skin == obj['active_skin']:
                    row.enabled = False
