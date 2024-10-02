from enum import IntEnum
import struct
from typing import List
from UnityPy.UnityPyBoost import unpack_vertexdata as unpack_vertexdata_boost
from UnityPy.enums import GfxPrimitiveType
from UnityPy.classes import StreamInfo, VertexData, Mesh


# Backported from UnityPy 47b1bde027fd79d78af3de4d5e3bebd05f8ceeb8 w/ Modifications
# Mesh.py: https://github.com/K0lb3/UnityPy/blob/47b1bde027fd79d78af3de4d5e3bebd05f8ceeb8/UnityPy/classes/Mesh.py
class MeshHelper:
    @staticmethod
    def GetFormatSize(format: int) -> int:
        if format in [
            VertexFormat.kVertexFormatFloat,
            VertexFormat.kVertexFormatUInt32,
            VertexFormat.kVertexFormatSInt32,
        ]:
            return 4
        elif format in [
            VertexFormat.kVertexFormatFloat16,
            VertexFormat.kVertexFormatUNorm16,
            VertexFormat.kVertexFormatSNorm16,
            VertexFormat.kVertexFormatUInt16,
            VertexFormat.kVertexFormatSInt16,
        ]:
            return 2
        elif format in [
            VertexFormat.kVertexFormatUNorm8,
            VertexFormat.kVertexFormatSNorm8,
            VertexFormat.kVertexFormatUInt8,
            VertexFormat.kVertexFormatSInt8,
        ]:
            return 1
        raise ValueError(format)

    @staticmethod
    def IsIntFormat(version, format: int) -> bool:
        if version[0] < 2017:
            return format == 4
        elif version[0] < 2019:
            return format >= 7
        else:
            return format >= 6

    @staticmethod
    def BytesToFloatArray(inputBytes, size, vformat: "VertexFormat") -> List[float]:
        if vformat == VertexFormat.kVertexFormatFloat:
            return struct.unpack(f">{'f'*(len(inputBytes)//4)}", inputBytes)
        elif vformat == VertexFormat.kVertexFormatFloat16:
            return struct.unpack(f">{'e'*(len(inputBytes)//2)}", inputBytes)
        elif vformat == VertexFormat.kVertexFormatUNorm8:
            return [byte / 255.0 for byte in inputBytes]
        elif vformat == VertexFormat.kVertexFormatSNorm8:
            return [max(((byte - 128) / 127.0), -1.0) for byte in inputBytes]
        elif vformat == VertexFormat.kVertexFormatUNorm16:
            return [
                x / 65535.0
                for x in struct.unpack(f">{'H'*(len(inputBytes)//2)}", inputBytes)
            ]
        elif vformat == VertexFormat.kVertexFormatSNorm16:
            return [
                max(((x - 32768) / 32767.0), -1.0)
                for x in struct.unpack(f">{'h'*(len(inputBytes)//2)}", inputBytes)
            ]

    @staticmethod
    def BytesToIntArray(inputBytes, size):
        if size == 1:
            return [x for x in inputBytes]
        elif size == 2:
            return [
                x for x in struct.unpack(f">{'h'*(len(inputBytes)//2)}", inputBytes)
            ]
        elif size == 4:
            return [
                x for x in struct.unpack(f">{'i'*(len(inputBytes)//4)}", inputBytes)
            ]

    @staticmethod
    def ToVertexFormat(format: int, version: List[int]) -> "VertexFormat":
        if version[0] < 2017:
            if format == VertexChannelFormat.kChannelFormatFloat:
                return VertexFormat.kVertexFormatFloat
            elif format == VertexChannelFormat.kChannelFormatFloat16:
                return VertexFormat.kVertexFormatFloat16
            elif format == VertexChannelFormat.kChannelFormatColor:  # in 4.x is size 4
                return VertexFormat.kVertexFormatUNorm8
            elif format == VertexChannelFormat.kChannelFormatByte:
                return VertexFormat.kVertexFormatUInt8
            elif format == VertexChannelFormat.kChannelFormatUInt32:  # in 5.x
                return VertexFormat.kVertexFormatUInt32
            else:
                raise ValueError(f"Failed to convert {format.name} to VertexFormat")
        elif version[0] < 2019:
            if format == VertexFormat2017.kVertexFormatFloat:
                return VertexFormat.kVertexFormatFloat
            elif format == VertexFormat2017.kVertexFormatFloat16:
                return VertexFormat.kVertexFormatFloat16
            elif (
                format == VertexFormat2017.kVertexFormatColor
                or format == VertexFormat2017.kVertexFormatUNorm8
            ):
                return VertexFormat.kVertexFormatUNorm8
            elif format == VertexFormat2017.kVertexFormatSNorm8:
                return VertexFormat.kVertexFormatSNorm8
            elif format == VertexFormat2017.kVertexFormatUNorm16:
                return VertexFormat.kVertexFormatUNorm16
            elif format == VertexFormat2017.kVertexFormatSNorm16:
                return VertexFormat.kVertexFormatSNorm16
            elif format == VertexFormat2017.kVertexFormatUInt8:
                return VertexFormat.kVertexFormatUInt8
            elif format == VertexFormat2017.kVertexFormatSInt8:
                return VertexFormat.kVertexFormatSInt8
            elif format == VertexFormat2017.kVertexFormatUInt16:
                return VertexFormat.kVertexFormatUInt16
            elif format == VertexFormat2017.kVertexFormatSInt16:
                return VertexFormat.kVertexFormatSInt16
            elif format == VertexFormat2017.kVertexFormatUInt32:
                return VertexFormat.kVertexFormatUInt32
            elif format == VertexFormat2017.kVertexFormatSInt32:
                return VertexFormat.kVertexFormatSInt32
            else:
                raise ValueError(f"Failed to convert {format.name} to VertexFormat")
        else:
            return VertexFormat(format)


class VertexChannelFormat(IntEnum):
    kChannelFormatFloat = 0
    kChannelFormatFloat16 = 1
    kChannelFormatColor = 2
    kChannelFormatByte = 3
    kChannelFormatUInt32 = 4


class VertexFormat2017(IntEnum):
    kVertexFormatFloat = 0
    kVertexFormatFloat16 = 1
    kVertexFormatColor = 2
    kVertexFormatUNorm8 = 3
    kVertexFormatSNorm8 = 4
    kVertexFormatUNorm16 = 5
    kVertexFormatSNorm16 = 6
    kVertexFormatUInt8 = 7
    kVertexFormatSInt8 = 8
    kVertexFormatUInt16 = 9
    kVertexFormatSInt16 = 10
    kVertexFormatUInt32 = 11
    kVertexFormatSInt32 = 12


class VertexFormat(IntEnum):
    kVertexFormatFloat = 0
    kVertexFormatFloat16 = 1
    kVertexFormatUNorm8 = 2
    kVertexFormatSNorm8 = 3
    kVertexFormatUNorm16 = 4
    kVertexFormatSNorm16 = 5
    kVertexFormatUInt8 = 6
    kVertexFormatSInt8 = 7
    kVertexFormatUInt16 = 8
    kVertexFormatSInt16 = 9
    kVertexFormatUInt32 = 10
    kVertexFormatSInt32 = 11


# Monkey patch old helper functions into the new classes
def VertexDataGetStreams(self, version):
    streamCount = 1
    if self.m_Channels:
        streamCount += max(x.stream for x in self.m_Channels)

    self.m_Streams = {}
    offset = 0
    for s in range(streamCount):
        chnMask = 0
        stride = 0
        for chn, m_Channel in enumerate(self.m_Channels):
            if m_Channel.stream == s:
                if m_Channel.dimension > 0:
                    chnMask |= 1 << chn  # Shift 1UInt << chn
                    stride += m_Channel.dimension * MeshHelper.GetFormatSize(
                        MeshHelper.ToVertexFormat(m_Channel.format, version)
                    )
        self.m_Streams[s] = StreamInfo(
            channelMask=chnMask,
            offset=offset,
            stride=stride,
            dividerOp=0,
            frequency=0,
        )
        offset += self.m_VertexCount * stride
        # static size_t align_streamSize (size_t size) { return (size + (kVertexStreamAlign-1)) & ~(kVertexStreamAlign-1)
        offset = (offset + (16 - 1)) & ~(16 - 1)  # (offset + (16u - 1u)) & ~(16u - 1u);


VertexData.GetStreams = VertexDataGetStreams


class BoneWeights4:
    def __init__(self):
        self.weight = [0.0] * 4
        self.boneIndex = [0] * 4


def InitMSkin(self):
    self.m_Skin = [BoneWeights4() for _ in range(self.m_VertexCount)]


Mesh.InitMSkin = InitMSkin


def MeshReadVertexData(self: Mesh):
    version = self.object_reader.version
    m_VertexData = self.m_VertexData
    m_VertexData.GetStreams(version)
    m_VertexCount = self.m_VertexCount = m_VertexData.m_VertexCount

    for chn, m_Channel in enumerate(m_VertexData.m_Channels):
        if m_Channel.dimension > 0:
            m_Stream = m_VertexData.m_Streams[m_Channel.stream]
            channelMask = bin(m_Stream.channelMask)[::-1]
            if channelMask[chn] == "1":
                if version[0] < 2018 and chn == 2 and m_Channel.format == 2:
                    m_Channel.dimension = 4

                componentByteSize = MeshHelper.GetFormatSize(
                    MeshHelper.ToVertexFormat(m_Channel.format, version)
                )
                swap = self.object_reader.reader.endian == "<" and componentByteSize > 1

                componentBytes = unpack_vertexdata_boost(
                    bytes(m_VertexData.m_DataSize),
                    componentByteSize,
                    m_VertexCount,
                    m_Stream.offset,
                    m_Stream.stride,
                    m_Channel.offset,
                    m_Channel.dimension,
                    swap,
                )

                if MeshHelper.IsIntFormat(version, m_Channel.format):
                    componentsIntArray = MeshHelper.BytesToIntArray(
                        componentBytes, componentByteSize
                    )
                else:
                    componentsFloatArray = MeshHelper.BytesToFloatArray(
                        componentBytes,
                        componentByteSize,
                        MeshHelper.ToVertexFormat(m_Channel.format, version),
                    )

                if version[0] >= 2018:
                    if chn == 0:  # kShaderChannelVertex
                        self.m_Vertices = componentsFloatArray
                    elif chn == 1:  # kShaderChannelNormal
                        self.m_Normals = componentsFloatArray
                    elif chn == 2:  # kShaderChannelTangent
                        self.m_Tangents = componentsFloatArray
                    elif chn == 3:  # kShaderChannelColor
                        self.m_Colors = componentsFloatArray
                    elif chn == 4:  # kShaderChannelTexCoord0
                        self.m_UV0 = componentsFloatArray
                    elif chn == 5:  # kShaderChannelTexCoord1
                        self.m_UV1 = componentsFloatArray
                    elif chn == 6:  # kShaderChannelTexCoord2
                        self.m_UV2 = componentsFloatArray
                    elif chn == 7:  # kShaderChannelTexCoord3
                        self.m_UV3 = componentsFloatArray
                    elif chn == 8:  # kShaderChannelTexCoord4
                        self.m_UV4 = componentsFloatArray
                    elif chn == 9:  # kShaderChannelTexCoord5
                        self.m_UV5 = componentsFloatArray
                    elif chn == 10:  # kShaderChannelTexCoord6
                        self.m_UV6 = componentsFloatArray
                    elif chn == 11:  # kShaderChannelTexCoord7
                        self.m_UV7 = componentsFloatArray
                    # 2018.2 and up
                    elif chn == 12:  # kShaderChannelBlendWeight
                        if not self.m_Skin:
                            self.InitMSkin()
                        for i in range(m_VertexCount):
                            for j in range(m_Channel.dimension):
                                self.m_Skin[i].weight[j] = componentsFloatArray[
                                    i * m_Channel.dimension + j
                                ]
                    elif chn == 13:  # kShaderChannelBlendIndices
                        if not self.m_Skin:
                            self.InitMSkin()
                        for i in range(m_VertexCount):
                            for j in range(m_Channel.dimension):
                                self.m_Skin[i].boneIndex[j] = componentsIntArray[
                                    i * m_Channel.dimension + j
                                ]
                else:
                    if chn == 0:  # kShaderChannelVertex
                        self.m_Vertices = componentsFloatArray
                    elif chn == 1:  # kShaderChannelNormal
                        self.m_Normals = componentsFloatArray
                    elif chn == 2:  # kShaderChannelColor
                        self.m_Colors = componentsFloatArray
                    elif chn == 3:  # kShaderChannelTexCoord0
                        self.m_UV0 = componentsFloatArray
                    elif chn == 4:  # kShaderChannelTexCoord1
                        self.m_UV1 = componentsFloatArray
                    elif chn == 5:
                        if version[0] >= 5:  # kShaderChannelTexCoord2
                            self.m_UV2 = componentsFloatArray
                        else:  # kShaderChannelTangent
                            self.m_Tangents = componentsFloatArray
                    elif chn == 6:  # kShaderChannelTexCoord3
                        self.m_UV3 = componentsFloatArray
                    elif chn == 7:  # kShaderChannelTangent
                        self.m_Tangents = componentsFloatArray


Mesh.ReadVertexData = MeshReadVertexData


def MeshRepackIndexBuffer(self):
    self.m_Use16BitIndices = self.m_IndexFormat == 0
    raw_indices = bytes(self.m_IndexBuffer)
    if self.m_Use16BitIndices:
        char = "H"
        index_size = 2
    else:
        char = "I"
        index_size = 4

    self.m_IndexBuffer = struct.unpack(
        f"<{len(raw_indices) // index_size}{char}", raw_indices
    )


Mesh.RepackIndexBuffer = MeshRepackIndexBuffer


def MeshGetTriangles(self):
    m_IndexBuffer = self.m_IndexBuffer
    m_Indices = self.m_Indices = getattr(self, "m_Indices", list())

    for m_SubMesh in self.m_SubMeshes:
        firstIndex = m_SubMesh.firstByte // 2
        if not self.m_Use16BitIndices:
            firstIndex //= 2

        indexCount = m_SubMesh.indexCount
        topology = m_SubMesh.topology
        if topology == GfxPrimitiveType.kPrimitiveTriangles:
            m_Indices.extend(
                m_IndexBuffer[firstIndex : firstIndex + indexCount - indexCount % 3]
            )

        elif (
            self.version[0] < 4 or topology == GfxPrimitiveType.kPrimitiveTriangleStrip
        ):
            # de-stripify :
            triIndex = 0
            for i in range(indexCount - 2):
                a, b, c = m_IndexBuffer[firstIndex + i : firstIndex + i + 3]

                # skip degenerates
                if a == b or a == c or b == c:
                    continue

                # do the winding flip-flop of strips :
                m_Indices.extend([b, a, c] if ((i & 1) == 1) else [a, b, c])
                triIndex += 3
            # fix indexCount
            m_SubMesh.indexCount = triIndex

        elif topology == GfxPrimitiveType.kPrimitiveQuads:
            for q in range(0, indexCount, 4):
                m_Indices.extend(
                    [
                        m_IndexBuffer[firstIndex + q],
                        m_IndexBuffer[firstIndex + q + 1],
                        m_IndexBuffer[firstIndex + q + 2],
                        m_IndexBuffer[firstIndex + q],
                        m_IndexBuffer[firstIndex + q + 2],
                        m_IndexBuffer[firstIndex + q + 3],
                    ]
                )
            # fix indexCount
            m_SubMesh.indexCount = indexCount // 2 * 3

        else:
            raise NotImplementedError(
                "Failed getting triangles. Submesh topology is lines or points."
            )


Mesh.GetTriangles = MeshGetTriangles


def MeshPreprocessData(self):
    self.ReadVertexData()
    self.RepackIndexBuffer()
    self.GetTriangles()
    return self


Mesh.PreprocessData = MeshPreprocessData


MESH_PROCESS_FLAG = "_preprocess_flag"


def read_mesh(mesh: Mesh) -> Mesh:
    """Populate the mesh data (e.g. vertices,indices,bone weights, etc) from the raw data.

    Args:
        mesh (Mesh): source mesh data. the modifications are done in-place.

    Returns:
        Mesh: processed mesh data
    """
    if not hasattr(mesh, MESH_PROCESS_FLAG):
        mesh._process_flag = True
        mesh.PreprocessData()
    return mesh
