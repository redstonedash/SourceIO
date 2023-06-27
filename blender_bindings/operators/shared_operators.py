import traceback
from hashlib import md5
from pathlib import Path
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       FloatProperty, StringProperty)
import bpy

from ..source1.mdl.v44.import_mdl import import_static_animations
from ...library.shared.content_providers.content_manager import ContentManager
from ...library.source2 import CompiledModelResource
from ...library.utils.path_utilities import find_vtx_cm
from ..source1.mdl import FileImport
from ..source1.mdl import put_into_collections as s1_put_into_collections
from ..source1.mdl.model_loader import import_model_from_files
from ..source1.mdl.v49.import_mdl import import_materials
from ..source2.vmdl_loader import load_model
from ..source2.vmdl_loader import \
    put_into_collections as s2_put_into_collections
from ..utils.utils import get_or_create_collection


def get_parent(collection):
    for pcoll in bpy.data.collections:
        if collection.name in pcoll.children:
            return pcoll
    return bpy.context.scene.collection


def get_collection(model_path: Path, *other_args):
    md_ = md5(model_path.as_posix().encode("ascii"))
    for key in other_args:
        if key:
            md_.update(key.encode("ascii"))
    key = md_.hexdigest()
    cache = bpy.context.scene.get("INSTANCE_CACHE", {})
    if key in cache:
        return cache[key]


def add_collection(model_path: Path, collection: bpy.types.Collection, *other_args):
    md_ = md5(model_path.as_posix().encode("ascii"))
    for key in other_args:
        if key:
            md_.update(key.encode("ascii"))
    key = md_.hexdigest()
    cache = bpy.context.scene.get("INSTANCE_CACHE", {})
    cache[key] = collection.name
    bpy.context.scene["INSTANCE_CACHE"] = cache


# noinspection PyPep8Naming
class ChangeSkin_OT_LoadEntity(bpy.types.Operator):
    bl_idname = "sourceio.load_placeholder"
    bl_label = "Load Entity"
    bl_options = {'UNDO'}

    use_bvlg: BoolProperty(default=True)

    def execute(self, context):
        content_manager = ContentManager()
        content_manager.deserialize(bpy.context.scene.get('content_manager_data', {}))
        unique_material_names = True
        master_instance_collection = get_or_create_collection("MASTER_INSTANCES_DO_NOT_EDIT",
                                                              bpy.context.scene.collection)
        master_instance_collection.hide_viewport = True
        master_instance_collection.hide_render = True
        win = bpy.context.window_manager

        win.progress_begin(0, len(context.selected_objects))
        for n, obj in enumerate(context.selected_objects):
            print(f'Loading {obj.name}')
            win.progress_update(n)
            if obj.get("entity_data", None):
                custom_prop_data = obj['entity_data']
                prop_path = custom_prop_data.get('prop_path', None)
                if prop_path is None:
                    continue
                model_type = Path(prop_path).suffix
                parent = get_parent(obj.users_collection[0])
                if model_type == '.vmdl_c':

                    instance_collection = get_collection(Path(prop_path))
                    if instance_collection:
                        collection = bpy.data.collections.get(instance_collection, None)
                        if collection is not None:
                            obj.instance_type = 'COLLECTION'
                            obj.instance_collection = collection
                            obj["entity_data"]["prop_path"] = None
                            continue

                    vmld_file = content_manager.find_file(prop_path)
                    if vmld_file:
                        # skin = custom_prop_data.get('skin', None)
                        model_resource = CompiledModelResource.from_buffer(vmld_file, Path(prop_path))
                        container = load_model(model_resource, custom_prop_data["scale"], lod_mask=1)
                        s2_put_into_collections(container, model_resource.name, master_instance_collection)
                        add_collection(Path(prop_path), container.collection)

                        obj.instance_type = 'COLLECTION'
                        obj.instance_collection = container.collection
                        obj["entity_data"]["prop_path"] = None
                        continue

                        # if container.armature:
                        #     armature = container.armature
                        #     armature.location = obj.location
                        #     armature.rotation_mode = "XYZ"
                        #     armature.rotation_euler = obj.rotation_euler
                        #     armature.scale = obj.scale
                        # else:
                        #     for ob in chain(container.objects,
                        #                     container.physics_objects):  # type:bpy.types.Object
                        #         ob.location = obj.location
                        #         ob.rotation_mode = "XYZ"
                        #         ob.rotation_euler = obj.rotation_euler
                        #         ob.scale = obj.scale
                        # for ob in container.objects:
                        #     if skin:
                        #         if str(skin) in ob['skin_groups']:
                        #             skin = str(skin)
                        #             skin_materials = ob['skin_groups'][skin]
                        #             current_materials = ob['skin_groups'][ob['active_skin']]
                        #             print(skin_materials, current_materials)
                        #             for skin_material, current_material in zip(skin_materials, current_materials):
                        #                 swap_materials(ob, skin_material[-63:], current_material[-63:])
                        #             ob['active_skin'] = skin
                        #         else:
                        #             print(f'Skin {skin} not found')
                        # master_collection = s2_put_into_collections(container, model_resource.name, collection, False)
                        # entity_data_holder = bpy.data.objects.new(model_resource.name + '_ENT', None)
                        # entity_data_holder['entity_data'] = {}
                        # entity_data_holder['entity_data']['entity'] = obj['entity_data']['entity']
                        # entity_data_holder.scale = obj.scale
                        # entity_data_holder.empty_display_size = 8 * custom_prop_data["scale"]
                        # entity_data_holder.hide_render = True
                        # entity_data_holder.hide_viewport = True
                        #
                        # if container.armature:
                        #     entity_data_holder.parent = container.armature
                        # elif container.objects:
                        #     entity_data_holder.parent = container.objects[0]
                        # elif container.physics_objects:
                        #     entity_data_holder.parent = container.physics_objects[0]
                        # else:
                        #     entity_data_holder.location = obj.location
                        #     entity_data_holder.rotation_euler = obj.rotation_euler
                        #     entity_data_holder.scale = obj.scale
                        #
                        # master_collection.objects.link(entity_data_holder)
                        # bpy.data.objects.remove(obj)
                    else:
                        self.report({'INFO'}, f"Model '{prop_path}' not found!")
                elif model_type == '.mdl':
                    default_anim = custom_prop_data["entity"].get("defaultanim", None)
                    prop_path = Path(prop_path)

                    instance_collection = get_collection(prop_path, default_anim)
                    if instance_collection:
                        collection = bpy.data.collections.get(instance_collection, None)
                        if collection is not None:
                            obj.instance_type = 'COLLECTION'
                            obj.instance_collection = collection
                            obj["entity_data"]["prop_path"] = None
                            continue

                    mdl_file = content_manager.find_file(prop_path)
                    vvd_file = content_manager.find_file(prop_path.with_suffix('.vvd'))
                    vvc_file = content_manager.find_file(prop_path.with_suffix('.vvc'))
                    phy_file = content_manager.find_file(prop_path.with_suffix('.phy'))
                    vtx_file = find_vtx_cm(prop_path, content_manager)
                    if mdl_file is None or vvd_file is None or vtx_file is None:
                        self.report({"WARNING"}, f"Failed to find mdl/vvd/vtx file for {obj.name}({prop_path}) prop")
                        continue
                    file_list = FileImport(mdl_file, vvd_file, vtx_file,
                                           vvc_file if vvc_file else None,
                                           phy_file if phy_file else None)
                    if not file_list.is_valid():
                        self.report({"WARNING"},
                                    f"Mdl file for {obj.name}({prop_path}) prop is invalid. Too small file or missing file")
                        continue
                    model_container = import_model_from_files(prop_path, file_list, 1.0, False, True,
                                                              unique_material_names=unique_material_names)
                    if model_container is None:
                        continue
                    import_materials(model_container.mdl, unique_material_names=unique_material_names, use_bvlg=context.scene.use_bvlg)

                    s1_put_into_collections(model_container, prop_path.stem, master_instance_collection, False)

                    if default_anim is not None and model_container.armature is not None:
                        try:
                            import_static_animations(content_manager, model_container.mdl, default_anim,
                                                     model_container.armature, 1.0)
                        except RuntimeError:
                            self.report({"WARNING"}, "Failed to load animation")
                            traceback.print_exc()

                    add_collection(prop_path, model_container.collection, default_anim)

                    obj.instance_type = 'COLLECTION'
                    obj.instance_collection = model_container.collection
                    obj["entity_data"]["prop_path"] = None
                    continue

                    # entity_data_holder = bpy.data.objects.new(model_container.mdl.header.name, None)
                    # entity_data_holder['entity_data'] = {}
                    # entity_data_holder['entity_data']['entity'] = obj['entity_data']['entity']
                    #
                    # master_collection = s1_put_into_collections(model_container, prop_path.stem, collection, False)
                    # master_collection.objects.link(entity_data_holder)
                    #
                    # if model_container.armature is not None:
                    #     armature = model_container.armature
                    #     armature.rotation_mode = "XYZ"
                    #     entity_data_holder.parent = armature
                    #
                    #     bpy.context.view_layer.update()
                    #     armature.parent = obj.parent
                    #     armature.matrix_world = obj.matrix_world.copy()
                    #     armature.rotation_euler[2] += math.radians(90)
                    # else:
                    #     if model_container.objects:
                    #         entity_data_holder.parent = model_container.objects[0]
                    #     else:
                    #         entity_data_holder.location = obj.location
                    #         entity_data_holder.rotation_euler = obj.rotation_euler
                    #         entity_data_holder.scale = obj.scale
                    #     for mesh_obj in model_container.objects:
                    #         mesh_obj.rotation_mode = "XYZ"
                    #         bpy.context.view_layer.update()
                    #         mesh_obj.parent = obj.parent
                    #         mesh_obj.matrix_world = obj.matrix_world.copy()
                    #
                    # for mesh_obj in model_container.objects:
                    #     mesh_obj['prop_path'] = prop_path
                    # if container is None:
                    #     import_materials(model_container.mdl, unique_material_names=unique_material_names)
                    # skin = custom_prop_data.get('skin', None)
                    # if skin:
                    #     for model in model_container.objects:
                    #         if str(skin) in model['skin_groups']:
                    #             skin = str(skin)
                    #             skin_materials = model['skin_groups'][skin]
                    #             current_materials = model['skin_groups'][model['active_skin']]
                    #             print(skin_materials, current_materials)
                    #             for skin_material, current_material in zip(skin_materials, current_materials):
                    #                 if unique_material_names:
                    #                     skin_material = f"{Path(model_container.mdl.header.name).stem}_{skin_material[-63:]}"[
                    #                                     -63:]
                    #                     current_material = f"{Path(model_container.mdl.header.name).stem}_{current_material[-63:]}"[
                    #                                        -63:]
                    #                 else:
                    #                     skin_material = skin_material[-63:]
                    #                     current_material = current_material[-63:]
                    #
                    #                 swap_materials(model, skin_material, current_material)
                    #             model['active_skin'] = skin
                    #         else:
                    #             print(f'Skin {skin} not found')
                    #
                    # bpy.data.objects.remove(obj)

        win.progress_end()

        return {'FINISHED'}


# noinspection PyPep8Naming
class SOURCEIO_OT_ChangeSkin(bpy.types.Operator):
    bl_idname = "sourceio.select_skin"
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
        prop_path = Path(obj['prop_path'])
        skin_materials = obj['skin_groups'][self.skin_name]
        current_materials = obj['skin_groups'][obj['active_skin']]
        unique_material_names = obj['unique_material_names']
        for skin_material, current_material in zip(skin_materials, current_materials):
            if unique_material_names:
                skin_material = f"{prop_path.stem}_{skin_material[-63:]}"[-63:]
                current_material = f"{prop_path.stem}_{current_material[-63:]}"[-63:]
            else:
                skin_material = skin_material[-63:]
                current_material = current_material[-63:]

            swap_materials(obj, skin_material, current_material)

    def handle_s2(self, obj):
        skin_material = obj['skin_groups'][self.skin_name]
        current_material = obj['skin_groups'][obj['active_skin']]

        mat_name = Path(skin_material).stem
        current_mat_name = Path(current_material).stem
        swap_materials(obj, mat_name, current_mat_name)


def swap_materials(obj, new_material_name, target_name):
    mat = bpy.data.materials.get(new_material_name, None) or bpy.data.materials.new(name=new_material_name)
    print(f'Swapping {target_name} with {new_material_name}')
    for n, obj_mat in enumerate(obj.data.materials):
        print(target_name, obj_mat.name)
        if obj_mat.name == target_name:
            print(obj_mat.name, "->", mat.name)
            obj.data.materials[n] = mat
            break


class UITools:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SourceIO"


# noinspection PyPep8Naming
class SOURCEIO_PT_Utils(UITools, bpy.types.Panel):
    bl_label = "SourceIO utils"
    bl_idname = "SOURCEIO_PT_Utils"

    def draw(self, context):
        pass
        # self.layout.label(text="SourceIO Utils")

    @classmethod
    def poll(cls, context):
        obj: bpy.types.Object = context.active_object
        return obj and (obj.get("entity_data", None) or obj.get("skin_groups", None))


# noinspection PyPep8Naming
class SOURCEIO_PT_EntityLoader(UITools, bpy.types.Panel):
    bl_label = 'Entity loader'
    bl_idname = 'SOURCEIO_PT_EntityLoader'
    bl_parent_id = "SOURCEIO_PT_Utils"

    @classmethod
    def poll(cls, context):
        obj: bpy.types.Object = context.active_object
        if not obj and not context.selected_objects:
            obj = context.selected_objects[0]
        return obj and obj.get("entity_data", None)

    def draw(self, context):
        self.layout.label(text="Entity loading")
        layout = self.layout.box()
        layout.prop(context.scene, "use_bvlg")
        obj: bpy.types.Object = context.active_object
        if obj is None and context.selected_objects:
            obj = context.selected_objects[0]
        if obj.get("entity_data", None):
            entity_data = obj['entity_data']
            row = self.layout.row()
            row.label(text=f'Total selected entities:')
            row.label(text=str(len([obj for obj in context.selected_objects if 'entity_data' in obj])))
            if entity_data.get('prop_path', False):
                box = self.layout.box()
                box.operator('sourceio.load_placeholder')


# noinspection PyPep8Naming
class SOURCEIO_PT_EntityInfo(UITools, bpy.types.Panel):
    bl_label = 'Entity Info'
    bl_idname = 'SOURCEIO_PT_EntityInfo'
    bl_parent_id = "SOURCEIO_PT_Utils"

    @classmethod
    def poll(cls, context):
        obj: bpy.types.Object = context.active_object
        if not obj and not context.selected_objects:
            obj = context.selected_objects[0]
        return obj and obj.get("entity_data", None)

    def draw(self, context):
        self.layout.label(text="Entity loading")
        obj: bpy.types.Object = context.active_object
        if obj is None and context.selected_objects:
            obj = context.selected_objects[0]
        if obj.get("entity_data", None):
            entity_data = obj['entity_data']
            entity_raw_data = entity_data.get('entity', {})
            box = self.layout.box()
            for k, v in entity_raw_data.items():
                row = box.row()
                row.label(text=f'{k}:')
                row.label(text=str(v))


class SOURCEIO_PT_SkinChanger(UITools, bpy.types.Panel):
    bl_label = 'Model skins'
    bl_idname = 'SOURCEIO_PT_SkinChanger'
    bl_parent_id = "SOURCEIO_PT_Utils"

    @classmethod
    def poll(cls, context):
        obj = context.active_object  # type:bpy.types.Object
        return obj and obj.get("skin_groups", None) is not None

    def draw(self, context):
        self.layout.label(text="Model skins")
        obj = context.active_object  # type:bpy.types.Object
        if obj.get("skin_groups", None):
            self.layout.label(text="Skins")
            box = self.layout.box()
            for skin, _ in obj['skin_groups'].items():
                row = box.row()
                op = row.operator('sourceio.select_skin', text=skin)
                op.skin_name = skin
                if skin == obj['active_skin']:
                    row.enabled = False


class SOURCEIO_PT_Scene(bpy.types.Panel):
    bl_label = 'SourceIO configuration'
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_default_closed = True

    def draw(self, context):
        layout = self.layout
        layout.label(text="SourceIO configuration")
        box = layout.box()
        box.label(text='Mounted folders')
        box2 = box.box()
        for mount_name, mount in bpy.context.scene.get('content_manager_data', {}).items():
            box2.label(text=f'{mount_name}: {mount}')
