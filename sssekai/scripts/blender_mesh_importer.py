# Config
SHADER_BLEND_FILE = r'C:\Users\mos9527\sssekai\sssekai\scripts\assets\SekaiShaderStandalone.blend'
PYTHON_PACKAGES_PATH = r'C:\Users\mos9527\AppData\Local\Programs\Python\Python310\Lib\site-packages'
import sys,os
try:
    import bpy
    import bpy_extras
    import bmesh
    from mathutils import Matrix, Quaternion as BlenderQuaternion, Vector, Euler
    # HACK: to get blender to use the system's python packges
    sys.path.append(PYTHON_PACKAGES_PATH)    
    BLENDER = True
except ImportError:
    # Stubs for debugging outside blender's python
    class Matrix: pass
    class BlenderQuaternion: pass
    class Vector:pass
    BLENDER = False
# Coordinate System | Forward |  Up  |  Left
# Unity:   LH, Y Up |   Z     |   Y  |   X
# Blender: RH, Z Up |  -Y     |   Z  |  -X
def swizzle_vector3(X,Y,Z):
    return Vector((-X,-Z,Y))
def swizzle_vector(vec):
    return swizzle_vector3(vec.X, vec.Y, vec.Z)
def swizzle_euler3(X,Y,Z):
    return Euler((X,Y,Z))
def swizzle_euler(euler, isDegrees = True):
    PIDIV180 = 3.141592653589793 / 180
    if isDegrees:  
        return swizzle_euler3(euler.X * PIDIV180, euler.Y * PIDIV180, euler.Z * PIDIV180)
    else:
        return swizzle_euler3(euler.X, euler.Y, euler.Z)
def swizzle_quaternion4(X,Y,Z,W):
    return BlenderQuaternion((W,X,Z,-Y)) # conjugate (W,-X,-Z,Y)
def swizzle_quaternion(quat):
    return swizzle_quaternion4(quat.X, quat.Y, quat.Z, quat.W)
import json
import tempfile
from typing import List, Dict, Tuple
from collections import defaultdict
from dataclasses import dataclass
import zlib
# Used for bone path (boneName) and blend shape name inverse hashing
def get_name_hash(name : str):
    return zlib.crc32(name.encode('utf-8'))
# The tables stored in the mesh's Custom Properties. Used by the animation importer.
KEY_BONE_NAME_HASH_TBL = 'sssekai_bone_name_hash_tbl' # Bone *full path hash* to bone name (Vertex Group name in blender lingo)
KEY_SHAPEKEY_NAME_HASH_TBL = 'sssekai_shapekey_name_hash_tbl' # ShapeKey name hash to ShapeKey names
BINDPOSE_MATRIX_TBL = 'sssekai_bindpose_matrix_tbl' # Bone name to bind pose matrix
# UnityPy deps
from UnityPy import Environment, config
from UnityPy.enums import ClassIDType
from UnityPy.classes import Mesh, SkinnedMeshRenderer, MeshRenderer, GameObject, Transform, Texture2D, Material
from UnityPy.math import Vector3, Quaternion as UnityQuaternion
# SSSekai deps
from sssekai.unity import SEKAI_UNITY_VERSION # XXX: expandusr does not work in Blender Python!
from sssekai.unity.AnimationClip import Track, read_animation, Animation, TransformType
config.FALLBACK_UNITY_VERSION = SEKAI_UNITY_VERSION
from sssekai.unity.AssetBundle import load_assetbundle
@dataclass
class Bone:
    name : str
    localPosition : Vector3
    localRotation : UnityQuaternion
    localScale : Vector3
    # Hierarchy. Built after asset import
    children : list # Bone
    global_path : str = ''
    global_transform : Matrix = None
    # Helpers
    def to_translation_matrix(self):
        return Matrix.Translation(swizzle_vector(self.localPosition))
    def to_trs_matrix(self):
        return Matrix.LocRotScale(
            swizzle_vector(self.localPosition),
            swizzle_quaternion(self.localRotation),
            Vector3(1,1,1)
        )
    def dfs_generator(self, root = None):
        def dfs(bone : Bone, parent : Bone = None, depth = 0):
            yield parent, bone, depth
            for child in bone.children:
                yield from dfs(child, bone, depth + 1)
        yield from dfs(root or self)        
    # Extra
    boneObj = None # Blender Bone
@dataclass
class Armature:
    name : str
    skinned_mesh_gameobject : GameObject = None
    root : Bone = None
    # Tables
    bone_path_hash_tbl : Dict[int,Bone] = None
    bone_name_tbl : Dict[str,Bone] = None
    # Helpers
    def get_bone_by_path(self, path : str):
        return self.bone_path_hash_tbl[get_name_hash(path)]
    def get_bone_by_name(self, name : str):
        return self.bone_name_tbl[name]
    def debug_print_bone_hierarchy(self):
        for parent, child, depth in self.root.dfs_generator():
            print('\t' * depth, child.name)
def search_env_meshes(env : Environment):
    '''(Partially) Loads the UnityPy Environment for further Mesh processing

    Args:
        env (Environment): UnityPy Environment

    Returns:
        Tuple[List[GameObject], Dict[str,Armature]]: Static Mesh GameObjects and Armatures
    '''
    # Collect all static meshes and skinned meshes's *root transform* object
    # UnityPy does not construct the Bone Hierarchy so we have to do it ourselves
    static_mesh_gameobjects : List[GameObject] = list() # No extra care needed
    transform_roots = []
    for obj in env.objects:
        data = obj.read()
        if obj.type == ClassIDType.GameObject and getattr(data,'m_MeshRenderer',None):
            static_mesh_gameobjects.append(data)
        if obj.type == ClassIDType.Transform:
            if hasattr(data,'m_Children') and not data.m_Father.path_id:
                transform_roots.append(data)
    # Collect all skinned meshes as Armature[s]
    # Note that Mesh maybe reused across Armatures, but we don't care...for now
    armatures = []
    for root in transform_roots:
        armature = Armature(root.m_GameObject.read().m_Name)
        armature.bone_path_hash_tbl = dict()
        armature.bone_name_tbl = dict()
        def dfs(root : Transform, parent : Bone = None):
            gameObject = root.m_GameObject.read()
            name = gameObject.m_Name        
            if getattr(gameObject,'m_SkinnedMeshRenderer',None):
                armature.skinned_mesh_gameobject = gameObject
            path_from_root = ''
            if parent and parent.global_path:
                path_from_root = parent.global_path + '/' + name
            elif parent:
                path_from_root = name
            bone = Bone(
                name,
                root.m_LocalPosition,
                root.m_LocalRotation,
                root.m_LocalScale,
                list(),
                path_from_root
            )
            armature.bone_name_tbl[name] = bone
            armature.bone_path_hash_tbl[get_name_hash(path_from_root)] = bone
            if not parent:
                armature.root = bone
            else:
                parent.children.append(bone)
            for child in root.m_Children:
                dfs(child.read(), bone)
        dfs(root)    
        if armature.skinned_mesh_gameobject:
            armatures.append(armature)
    return static_mesh_gameobjects, armatures
def search_env_animations(env : Environment):
    '''Searches the Environment for AnimationClips

    Args:
        env (Environment): UnityPy Environment

    Returns:
        List[AnimationClip]: AnimationClips
    '''
    animations = []
    for asset in env.assets:
        for obj in asset.get_objects():
            data = obj.read()
            if obj.type == ClassIDType.AnimationClip:
                animations.append(data)
    return animations

def import_mesh(name : str, data: Mesh, skinned : bool = False, bone_path_tbl : Dict[str,Bone] = None):
    '''Imports the mesh data into blender.

    Takes care of the following:
    - Vertices (Position + Normal) and indices (Trig Faces)
    - UV Map
    Additonally, for Skinned meshes:
    - Bone Indices + Bone Weights
    - Blend Shape / Shape Keys

    Args:
        name (str): Name for the created Blender object
        data (Mesh): Source UnityPy Mesh data
        skinned (bool, optional): Whether the Mesh has skinning data, i.e. attached to SkinnedMeshRenderer. Defaults to False.

    Returns:
        Tuple[bpy.types.Mesh, bpy.types.Object]: Created mesh and its parent object
    '''
    print('* Importing Mesh', data.name, 'Skinned=', skinned)
    bpy.ops.object.mode_set(mode='OBJECT')
    mesh = bpy.data.meshes.new(name=data.name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    vtxFloats = int(len(data.m_Vertices) / data.m_VertexCount)
    normalFloats = int(len(data.m_Normals) / data.m_VertexCount)
    uvFloats = int(len(data.m_UV0) / data.m_VertexCount)
    colorFloats = int(len(data.m_Colors) / data.m_VertexCount)
    # Bone Indices + Bone Weights
    deform_layer = None
    if skinned:
        for boneHash in data.m_BoneNameHashes:
            # boneHash is the CRC32 hash of the full bone path
            # i.e Position/Hips/Spine/Spine1/Spine2/Neck/Head
            group_name = bone_path_tbl[boneHash].name   
            obj.vertex_groups.new(name=group_name)
        deform_layer = bm.verts.layers.deform.new()
        # Animations uses the hash to identify the bone
        # so this has to be stored in the metadata as well
        mesh[KEY_BONE_NAME_HASH_TBL] = json.dumps({k:v.name for k,v in bone_path_tbl.items()},ensure_ascii=False)
    # Vertex position & vertex normal (pre-assign)
    for vtx in range(0, data.m_VertexCount):        
        vert = bm.verts.new(swizzle_vector3(
            data.m_Vertices[vtx * vtxFloats], # x,y,z
            data.m_Vertices[vtx * vtxFloats + 1],
            data.m_Vertices[vtx * vtxFloats + 2]            
        ))
        # Blender always generates normals automatically
        # Custom normals needs a bit more work
        # See below for normals_split... calls
        # XXX why is this flipped?
        vert.normal = swizzle_vector3(
            -1 * data.m_Normals[vtx * normalFloats],
            -1 * data.m_Normals[vtx * normalFloats + 1],
            -1 * data.m_Normals[vtx * normalFloats + 2]
        )
        if deform_layer:
            for i in range(4):
                skin = data.m_Skin[vtx]
                if skin.weight[i] == 0:
                    break # Weight is sorted
                vertex_group_index = skin.boneIndex[i]
                vert[deform_layer][vertex_group_index] = skin.weight[i]
    bm.verts.ensure_lookup_table()
    # Indices
    for idx in range(0, len(data.m_Indices), 3):
        face = bm.faces.new([bm.verts[data.m_Indices[idx + j]] for j in range(3)])
        face.smooth = True
    bm.to_mesh(mesh)
    # UV Map
    uv_layer = mesh.uv_layers.new()
    mesh.uv_layers.active = uv_layer
    for face in mesh.polygons:
        for vtx, loop in zip(face.vertices, face.loop_indices):
            uv_layer.data[loop].uv = (
                data.m_UV0[vtx * uvFloats], 
                data.m_UV0[vtx * uvFloats + 1]
            )
    # Vertex Color
    vertex_color = mesh.color_attributes.new(name='Vertex Color',type='FLOAT_COLOR',domain='POINT')
    for vtx in range(0, data.m_VertexCount):
        color = [data.m_Colors[vtx * colorFloats + i] for i in range(colorFloats)]
        vertex_color.data[vtx].color = color
    # Assign vertex normals
    mesh.create_normals_split()
    normals = [(0,0,0) for l in mesh.loops]
    for i, loop in enumerate(mesh.loops):
        normal = bm.verts[loop.vertex_index].normal
        normal.normalize()
        normals[i] = normal
    mesh.normals_split_custom_set(normals)
    mesh.use_auto_smooth = True   
    # Blend Shape / Shape Keys
    if data.m_Shapes.channels:
        obj.shape_key_add(name="Basis")
        keyshape_hash_tbl = dict()
        for channel in data.m_Shapes.channels:
            shape_key = obj.shape_key_add(name=channel.name)
            keyshape_hash_tbl[channel.nameHash] = channel.name
            for frameIndex in range(channel.frameIndex, channel.frameIndex + channel.frameCount):
                # fullWeight = mesh_data.m_Shapes.fullWeights[frameIndex]
                shape = data.m_Shapes.shapes[frameIndex]
                for morphedVtxIndex in range(shape.firstVertex,shape.firstVertex + shape.vertexCount):
                    morpedVtx = data.m_Shapes.vertices[morphedVtxIndex]
                    targetVtx : bpy.types.ShapeKeyPoint = shape_key.data[morpedVtx.index]
                    targetVtx.co += swizzle_vector(morpedVtx.vertex)                    
        # Like boneHash, do the same thing with blend shapes
        mesh[KEY_SHAPEKEY_NAME_HASH_TBL] = json.dumps(keyshape_hash_tbl,ensure_ascii=False)
    bm.free()      
    return mesh, obj
def import_armature(name : str, data : Armature):
    '''Imports the Armature data generated into blender

    NOTE: Unused bones will not be imported since they have identity transforms and thus
    cannot have their own head-tail vectors. It's worth noting though that they won't affect
    the mesh anyway.

    Args:
        name (str): Armature Object name
        data (Armature): Armature as genereated by previous steps
    
    Returns:
        Tuple[bpy.types.Armature, bpy.types.Object]: Created armature and its parent object
    '''
    armature = bpy.data.armatures.new(name)
    armature.display_type = 'STICK'
    armature.relation_line_position = 'HEAD'

    obj = bpy.data.objects.new(name, armature)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    # HACK: *Seems like* the only useful root bone is 'Position' (which is the root of the actual skeleton)    
    for bone in data.root.children:
        bone : Bone
        if bone.name == 'Position':
            print('* Found valid armature root', bone.name, 'at', bone.global_path, 'with', len(bone.children), 'children')
            bone.global_transform = Matrix.Identity(4)
            # Build global transforms
            # I think using the inverse of m_BindPose could work too
            # but I kinda missed it until I implemented all this so...
            for parent, child, _ in bone.dfs_generator():
                if parent:
                    child.global_transform = parent.global_transform @ child.to_trs_matrix()
                else:
                    child.global_transform = child.to_trs_matrix()
            # Build bone hierarchy in blender
            for parent, child, _ in bone.dfs_generator():
                bbone = armature.edit_bones.new(child.name)
                bbone.use_local_location = False
                bbone.use_relative_parent = False                
                bbone.use_connect = False
                bbone.use_deform = True
                bbone[BINDPOSE_MATRIX_TBL] = [v for col in child.to_trs_matrix() for v in col]
                child.boneObj = bbone               
                if parent:
                    bbone.head = parent.global_transform.translation
                    bbone.parent = parent.boneObj
                else:
                    bbone.head = child.global_transform.translation + Vector((0,0,0.01)) # Otherwise the bone disappears!
                bbone.tail = child.global_transform.translation
    bpy.ops.object.mode_set(mode='OBJECT')
    return armature, obj
def import_texture(name : str, data : Texture2D):
    '''Imports Texture2D assets into blender

    Args:
        name (str): asset name
        data (Texture2D): source texture

    Returns:
        bpy.types.Image: Created image
    '''
    with tempfile.NamedTemporaryFile(suffix='.bmp',delete=False) as temp:
        print('* Saving Texture', name, 'to', temp.name)
        data.image.save(temp)
        temp.close()
        img = bpy.data.images.load(temp.name, check_existing=True)        
        img.name = name
        print('* Imported Texture', name)
        return img
def import_material(name : str,data : Material):
    '''Imports Material assets into blender. 
    A custom shader / material block is imported from the SekaiShaderStandalone.blend file.
    

    Args:
        name (str): material name
        data (Material): UnityPy Material

    Returns:
        bpy.types.Material: Created material        
    '''
    if not 'SekaiShader' in bpy.data.materials:
        print('! No SekaiShader found. Importing from source.')
        with bpy.data.libraries.load(SHADER_BLEND_FILE, link=False) as (data_from, data_to):
            data_to.materials = data_from.materials
            print('! Loaded shader blend file.')
    material = bpy.data.materials["SekaiShader"].copy()
    material.name = name
    def setup_texnode(ppTexture):
        texCoord = material.node_tree.nodes.new('ShaderNodeTexCoord')
        uvRemap = material.node_tree.nodes.new('ShaderNodeMapping')
        uvRemap.inputs[1].default_value[0] = ppTexture.m_Offset.X
        uvRemap.inputs[1].default_value[1] = ppTexture.m_Offset.Y
        uvRemap.inputs[3].default_value[0] = ppTexture.m_Scale.X
        uvRemap.inputs[3].default_value[1] = ppTexture.m_Scale.Y
        texture : Texture2D = ppTexture.m_Texture.read()
        texNode = material.node_tree.nodes.new('ShaderNodeTexImage')
        texNode.image = import_texture(texture.name, texture)
        material.node_tree.links.new(texCoord.outputs['UV'], uvRemap.inputs['Vector'])
        material.node_tree.links.new(uvRemap.outputs['Vector'], texNode.inputs['Vector'])
        return texNode
    sekaiShader = material.node_tree.nodes['Group']
    mainTex = setup_texnode(data.m_SavedProperties.m_TexEnvs['_MainTex'])
    shadowTex = setup_texnode(data.m_SavedProperties.m_TexEnvs['_ShadowTex'])
    valueTex = setup_texnode(data.m_SavedProperties.m_TexEnvs['_ValueTex'])
    material.node_tree.links.new(mainTex.outputs['Color'], sekaiShader.inputs[0])
    material.node_tree.links.new(shadowTex.outputs['Color'], sekaiShader.inputs[1])
    material.node_tree.links.new(valueTex.outputs['Color'], sekaiShader.inputs[2])
    return material

def check_is_object_sssekai_imported_armature(arm_obj):
    assert arm_obj.type == 'ARMATURE', "Please select an armature"
    mesh_obj = arm_obj.children[0]
    mesh = mesh_obj.data
    assert KEY_BONE_NAME_HASH_TBL in mesh or KEY_SHAPEKEY_NAME_HASH_TBL in mesh, "This armature is not imported by SSSekai."

def import_animation(name : str, data : Animation):
    arm_obj = bpy.context.active_object
    mesh_obj = arm_obj.children[0]
    mesh = mesh_obj.data    
    bone_table = json.loads(mesh[KEY_BONE_NAME_HASH_TBL]) if KEY_BONE_NAME_HASH_TBL in mesh else dict()
    shapekey_table = json.loads(mesh[KEY_SHAPEKEY_NAME_HASH_TBL]) if KEY_SHAPEKEY_NAME_HASH_TBL in mesh else dict()
    print('* Importing Animation', name)
    bpy.ops.object.mode_set(mode='EDIT')    
    # Note: The transforms are all done in the bone's parent space
    local_space_mat = dict()
    arm_space_mat = dict()
    for bone in arm_obj.data.edit_bones:
        local_space_mat[bone.name] = Matrix(tuple(bone[BINDPOSE_MATRIX_TBL][n:n+4] for n in range(0, 16, 4)))
        arm_space_mat[bone.name] = bone.matrix        
    bpy.ops.object.mode_set(mode='POSE')
    arm_obj.animation_data_clear()
    arm_obj.animation_data_create()
    bpy.context.scene.render.fps = int(data.Framerate)
    print('* Blender FPS:', bpy.context.scene.render.fps)
    def time_to_frame(time : float):
        return int(time * bpy.context.scene.render.fps) + 1
    def debug_format_trs_matrix(mat: Matrix):
        t,r,s = mat.decompose()
        return 'T: %s R: %s Q: %s S: %s' % (t,r.to_euler(),r,s)   
    def to_pose_quaternion(bone : bpy.types.PoseBone, quat : BlenderQuaternion):
        g_mat = arm_space_mat[bone.name]
        result = g_mat @ quat.to_matrix().to_4x4() @ g_mat.inverted()
        g_parent_rot = arm_space_mat[bone.parent.name].to_quaternion() if bone.parent else BlenderQuaternion()
        return result.to_quaternion() @ g_parent_rot.inverted() 
    def to_pose_translation(bone : bpy.types.PoseBone, vec : Vector):
        g_mat = arm_space_mat[bone.name]
        g_trans = g_mat.to_translation()
        result = g_mat @ Matrix.Translation(vec) @ g_mat.inverted()
        g_p_trans = arm_space_mat[bone.parent.name].to_translation() if bone.parent else Vector()        
        return result.to_translation() + g_trans - g_p_trans
    # XXX: These shouldn't work
    def to_pose_euler(bone : bpy.types.PoseBone, euler : Euler):
        euler0 = local_space_mat[bone.name].to_euler()
        return Euler((euler.x - euler0.x, euler.y - euler0.y, euler.z - euler0.z))
    def to_pose_scale(bone : bpy.types.PoseBone, scale : Vector):
        scale0 = local_space_mat[bone.name].to_scale()
        return Vector((scale.x / scale0.x, scale.y / scale0.y, scale.z / scale0.z))
    # Transform (Bones)
    def add_transform(transformType, tracks):
        for boneHash, track in tracks.items():
            boneHash = str(boneHash) # json keys are always strings
            bone = arm_obj.pose.bones[bone_table[str(boneHash)]]
            if not boneHash in bone_table:
                print('! Discarding bone', boneHash, 'because it is not in the bone table. Results may be incorrect.')
                continue
            else:
                # print('* Bone %s Rotation Curves: %d Translation Curves: %d Scaling Curves: %d' % (bone.name, len(track.Curve), len(track.Curve), len(track.Curve)))
                pass
            if transformType == TransformType.Rotation:
                bone.rotation_mode = 'QUATERNION'
                for keyframe in track.Curve:
                    bone.rotation_quaternion = to_pose_quaternion(bone, swizzle_quaternion(keyframe.value))                    
                    bone.keyframe_insert(data_path='rotation_quaternion', frame=time_to_frame(keyframe.time))
            if transformType == TransformType.Translation:
                for keyframe in track.Curve:
                    bone.location = to_pose_translation(bone, swizzle_vector(keyframe.value))
                    print('<%s translation local %s pose %s>' % (bone.name, swizzle_vector(keyframe.value), bone.location))
                    bone.keyframe_insert(data_path='location', frame=time_to_frame(keyframe.time))
            if transformType == TransformType.Scaling:
                for keyframe in track.Curve:
                    bone.scale = to_pose_scale(bone, swizzle_vector(keyframe.value))
                    bone.keyframe_insert(data_path='scale', frame=time_to_frame(keyframe.time))
            if transformType == TransformType.EulerRotation:
                bone.rotation_mode = 'XYZ'
                for keyframe in track.Curve:
                    bone.rotation_euler = to_pose_euler(bone, swizzle_euler(keyframe.value))                    
                    bone.keyframe_insert(data_path='rotation_euler',frame=time_to_frame(keyframe.time))
    if TransformType.Translation in data.TransformTracks:
        add_transform(TransformType.Translation, data.TransformTracks[TransformType.Translation])
    if TransformType.Rotation in data.TransformTracks:
        add_transform(TransformType.Rotation, data.TransformTracks[TransformType.Rotation])
    if TransformType.EulerRotation in data.TransformTracks:
        add_transform(TransformType.EulerRotation, data.TransformTracks[TransformType.EulerRotation])
    if TransformType.Scaling in data.TransformTracks:
        add_transform(TransformType.Scaling, data.TransformTracks[TransformType.Scaling])
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

if __name__ == "__main__":
    if BLENDER:
        bpy.utils.register_class(SSSekaiBlenderMeshImportOperator)
        def import_func(self, context):
            self.layout.operator(SSSekaiBlenderMeshImportOperator.bl_idname, text="SSSekai Mesh Importer")
        bpy.types.TOPBAR_MT_file_import.append(import_func)
    # ---- TESTING ----
    if BLENDER:
        arm_obj = bpy.context.active_object
        check_is_object_sssekai_imported_armature(arm_obj)    
    with open(r"C:\Users\mos9527\Desktop\Anim\Anim_Data\sharedassets0.assets",'rb') as f:
        ab = load_assetbundle(f)
        animations = search_env_animations(ab)
        for animation in animations:
            print('* Found AnimationClip:', animation.name)
            if '_00' in animation.name:
                print('* Reading AnimationClip:', animation.name)
                print('* Byte size (compressed):',animation.byte_size)
                clip = read_animation(animation)  
                import_animation(animation.name, clip)
                break
