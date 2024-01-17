from common import *
if BLENDER:
    from animation import import_armature_animation,import_keyshape_animation
    from asset import import_material, import_armature, import_mesh, import_texture, search_env_animations,search_env_meshes
if BLENDER:
    class SSSekaiBlenderMeshImportOperator(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
        bl_idname = "sssekai.import_mesh"
        bl_label = "SSSekai Mesh Importer"
        filename_ext = "*.*"
        def execute(self, context):
            ab_file = open(self.filepath, 'rb')
            print('* Loading', self.filepath)
            env = load_assetbundle(ab_file)
            static_mesh_gameobjects, armatures = search_env_meshes(env)

            for mesh_go in static_mesh_gameobjects:
                mesh_rnd : MeshRenderer = mesh_go.m_MeshRenderer.read()
                mesh_data : Mesh = mesh_rnd.m_Mesh.read()    
                mesh, obj = import_mesh(mesh_go.name, mesh_data,False)    
                print('* Created Static Mesh', mesh_data.name)

            for armature in armatures:
                mesh_rnd : SkinnedMeshRenderer = armature.skinned_mesh_gameobject.m_SkinnedMeshRenderer.read()
                mesh_data : Mesh = mesh_rnd.m_Mesh.read()
                armInst, armObj = import_armature('%s_Armature' % armature.name ,armature)
                mesh, obj = import_mesh(armature.name, mesh_data,True, armature.bone_path_hash_tbl)
                obj.parent = armObj
                obj.modifiers.new('Armature', 'ARMATURE').object = armObj
                for ppmat in mesh_rnd.m_Materials:
                    material : Material = ppmat.read()
                    asset = import_material(material.name, material)
                    obj.data.materials.append(asset)
                    print('* Created Material', material.name)
                print('* Created Armature', armature.name, 'for Skinned Mesh', mesh_data.name)    
            
            return {'FINISHED'}    

def check_is_object_sssekai_imported_armature(arm_obj):
    assert arm_obj and arm_obj.type == 'ARMATURE', "Please select an armature"
    mesh_obj = arm_obj.children[0]
    mesh = mesh_obj.data
    assert KEY_BONE_NAME_HASH_TBL in mesh or KEY_SHAPEKEY_NAME_HASH_TBL in mesh, "This armature is not imported by SSSekai."

if __name__ == "__main__":
    if BLENDER:
        bpy.utils.register_class(SSSekaiBlenderMeshImportOperator)
        def import_func(self, context):
            self.layout.operator(SSSekaiBlenderMeshImportOperator.bl_idname, text="SSSekai Mesh Importer")
        bpy.types.TOPBAR_MT_file_import.append(import_func)
    # ---- TESTING ----
    with open(r"F:\Sekai\live_pv\timeline\0001\character",'rb') as f:
        ab = load_assetbundle(f)
        animations = search_env_animations(ab)
        for animation in animations:
            print('* Found AnimationClip:', animation.name)
            if 'face' in animation.name:
                print('* Reading AnimationClip:', animation.name)
                print('* Byte size (compressed):',animation.byte_size)
                print('* Loading...')
                clip = read_animation(animation)  
                print('* Importing...')
                import_keyshape_animation(animation.name, clip, bpy.context.active_object)
                break

