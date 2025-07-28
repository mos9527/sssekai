from base64 import b64decode, b64encode
from struct import unpack as s_unpack
from io import BytesIO
from collections import defaultdict
from typing import Generator, Tuple, TypeVar, List
import math, gzip
import msgpack

RLA_VERSIONS = [(1, 0), (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7)]

read_int = lambda stream, nbytes, signed=False: int.from_bytes(
    stream.read(nbytes), "little", signed=signed
)
read_float = lambda stream: s_unpack("<f", stream.read(4))[0]


class SSEDataLengthOutOfRangeException(Exception):
    needed: int
    current: int

    def __init__(self, needed, current):
        self.needed = needed
        self.current = current
        super().__init__(f"Needed {needed} bytes, but only {current} bytes available.")


class SSEMissingSplitPacketException(Exception):
    missing: List[Tuple[object, int]]  # (timeStamp, splitId)

    def __init__(self, missing):
        self.missing = missing
        super().__init__(f"Missing %d split packet(s): %s" % (len(missing), missing))


# Sekai_Streaming_StreamingCommon__CheckHeader
def decode_buffer_base64(buffer: bytes) -> tuple[int, bytes]:
    """Decodes the 'RTVL' SSE Message payload into a header signature and data.

    Args:
        buffer (bytes): Encoded buffer

    Raises:
        SSEDataLengthOutOfRangeException: If the buffer length does not match the expected length.

    Returns:
        ((splitId, splitIndex, splitNum, dataLength, totalDataLength, base64) or None, decoder signature, data in decoded bytes)
    """
    # They really want you to believe it's Base64...
    # [4 bytes: RTVL][6 bytes : length in hex][Base64 T/F][Split T/F][3 bytes: Signature][data, Base64]
    # ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ 15 bytes
    # Sekai_Streaming_StreamingCommon__cctor
    SYM_HEADER = b"RTVL"
    SYM_TRUE = b"T"
    SYM_FALSE = b"F"
    stream = BytesIO(buffer)
    assert stream.read(4) == SYM_HEADER, "bad header"
    encoded_length = stream.read(6)
    encoded_length = int(encoded_length, 16)
    is_base64_encoded = stream.read(1) == SYM_TRUE
    is_split = stream.read(1) == SYM_TRUE
    header_signature = int(stream.read(3).decode(), 10)
    data = stream.read()
    current_length = len(data) + 15
    if current_length != encoded_length:
        raise SSEDataLengthOutOfRangeException(encoded_length, current_length)
    if is_split:
        __sizes_pre = (0, 5, 10, 15, 25, 35)
        splitInfo = data[: __sizes_pre[-1]]
        splitId, splitIndex, splitNum, dataLength, totalDataLength = map(
            int,
            (
                splitInfo[__sizes_pre[i] : __sizes_pre[i + 1]].decode()
                for i in range(len(__sizes_pre) - 1)
            ),
        )
        data = data[__sizes_pre[-1] :]
        return (
            (
                splitId,
                splitIndex,
                splitNum,
                dataLength,
                totalDataLength,
                is_base64_encoded,
            ),
            header_signature,
            data,
        )
    else:
        if is_base64_encoded:
            data = b64decode(data)
        return None, header_signature, data


# Sekai_Streaming_SubscribeDecoder__Deserialize
def decode_buffer_payload(buffer: bytes) -> tuple[int, bytes]:
    """Decodes the decoded data payload (in binary form) into a decoder signature and payload data.

    Args:
        buffer (bytes): Decoded buffer

    Returns:
        (int, bytes): Decoder signature and decoded payload data. The signature should match the Header Signature.
    """
    stream = BytesIO(buffer)
    decoder_signature = read_int(stream, 1)
    unk1 = read_int(stream, 4)
    if not unk1:
        unk2 = read_int(stream, 4)
        if unk2:
            payload = stream.read()
            payload = gzip.decompress(payload)
            return decoder_signature, payload
    return decoder_signature, stream.read()


# Sekai_Streaming_StreamingData__Deserialize
def decode_streaming_data(
    version: tuple, decoder_signature, buffer, strict=True
) -> dict:
    """Decodes the streaming data payload into a dictionary.

    Args:
        version (tuple): RLA version
        decoder_signature (int): Decoder signature
        buffer (bytes): Decoded payload data
        strict (bool, optional): If False, incomplete packets will be returned as is. Defaults to True.

    Raises:
        Exception: If the packet is incomplete and strict is True.

    Returns:
        dict: Parsed streaming data payload
    """
    stream = BytesIO(buffer)
    n_mask_offset = read_int(stream, 4)
    n_init_pos = stream.tell()
    stream.seek(n_mask_offset)
    n_mask_length = read_int(stream, 2)
    bitmask = stream.read(n_mask_length)
    # assert not stream.read() # EOF
    stream.seek(n_init_pos)
    # CP_Serialize_SerializableValueSet
    mask_i = -1

    def get_next_mask():
        nonlocal mask_i
        mask_i += 1
        return bitmask[mask_i // 8] & (1 << (mask_i % 8)) != 0

    get_next_pred = lambda: get_next_mask() | (get_next_mask() << 1)
    get_next_byte = lambda: [
        lambda: 0,
        lambda: 1,
        lambda: -1,
        lambda: read_int(stream, 1),
    ][
        get_next_pred()
    ]()  # ReadByte
    get_next_ushort = lambda: [
        lambda: 0.0,
        lambda: 0.0,
        lambda: read_int(stream, 1),
        lambda: read_int(stream, 2),
    ][
        get_next_pred()
    ]()  # ReadUShort
    get_next_short = lambda: [
        lambda: 0.0,
        lambda: 0.0,
        lambda: read_int(stream, 1, True),
        lambda: read_int(stream, 2),
    ][
        get_next_pred()
    ]()  # ReadShort
    get_next_int = lambda: [
        lambda: 0,
        lambda: read_int(stream, 1),
        lambda: read_int(stream, 1, True),
        lambda: read_int(stream, 4),
    ][
        get_next_pred()
    ]()  # ReadInt
    get_next_long = lambda: [
        lambda: 0,
        lambda: read_int(stream, 1),
        lambda: read_int(stream, 2),
        lambda: read_int(stream, 8),
    ][
        get_next_pred()
    ]()  # ReadLong
    get_next_float = lambda: [
        lambda: 0.0,
        lambda: 0.0,
        lambda: 3.4028e38,
        lambda: read_float(stream),
    ][
        get_next_pred()
    ]()  # ReadSingle
    get_next_vector3 = lambda: (
        get_next_float(),
        get_next_float(),
        get_next_float(),
    )  # ReadVector3
    get_next_ushort_vector3 = lambda: (
        get_next_ushort() * 0.01,
        get_next_ushort() * 0.01,
        get_next_ushort() * 0.01,
    )  # ReadUShortVector3
    get_next_quaternion = lambda: (
        get_next_float(),
        get_next_float(),
        get_next_float(),
        get_next_float(),
    )  # ReadQuaternion
    get_next_tiny_int = lambda type: {
        "+": lambda: read_int(stream, 2),
        "*": lambda: read_int(stream, 1, True),
        ")": lambda: read_int(stream, 1),
    }[
        type
    ]()  # ReadTinyInt
    get_next_string = lambda: (
        stream.read(get_next_tiny_int(chr(read_int(stream, 1)))).decode()
        if get_next_pred()
        else None
    )  # ReadString

    # HACK: Workaround for incomplete packets.
    def gen_exception_handler(generator):
        try:
            for item in generator:
                yield item
        except Exception as e:
            # XXX: This shouldn't happen unless the packet is corrupted.
            if strict:
                raise e
            else:
                return

    gen_get_next_array = lambda reader: (
        reader() for _ in range(get_next_int())
    )  # ReadArray<T>
    get_next_array = lambda reader: list(
        gen_exception_handler(gen_get_next_array(reader))
    )
    # Sekai_Streaming_StreamingData__Deserialize
    assert get_next_byte() == decoder_signature, "bad signature"
    compress_type = get_next_int()
    sequence_no = get_next_int()
    target_time = get_next_long()
    # StreamingData$$ReadValue implementations
    deg_to_rad = lambda value: tuple(deg * (math.pi / 180) for deg in value)
    get_next_deg_as_rad = lambda: deg_to_rad(
        get_next_ushort_vector3()
    )  # Eulers [0, 2pi]
    get_next_pose_data = lambda: {
        "bodyPosition": get_next_vector3(),
        "bodyRotation": get_next_deg_as_rad(),  # Eulers
        **(
            {
                "musicItemPropPosition": get_next_vector3(),
                "musicItemPropRotation": get_next_deg_as_rad(),
            }
            if version >= (1, 1)
            else {}
        ),
        "boneDatas": get_next_array(get_next_deg_as_rad),  # Eulers [0, 2pi]
        "shapeDatas": get_next_array(get_next_float),  # [0,100]
        **(
            {"propBoneDatas": get_next_array(get_next_deg_as_rad)}  # Eulers [0, 2pi]
            if version >= (1, 1)
            else {}
        ),
        "heightOffset": get_next_short() * 0.01,
        "isActive": get_next_mask(),
        "useActiveFx": get_next_mask(),
        **({"isEyeLookAt": get_next_mask()} if version >= (1, 4) else {}),
    }
    match decoder_signature:
        case 0:
            # Sekai_Streaming_MotionData
            timeStamps = get_next_array(get_next_long) if get_next_pred() == 2 else None
            poses = get_next_array(get_next_pose_data)
            return {"type": "MotionData", "timeStamps": timeStamps, "poses": poses}
        case 1:
            # Sekai_Streaming_MotionCaptureData
            read_character_capture_data = lambda: {
                "id": get_next_int(),
                "timestamp": get_next_long(),
                "pose": get_next_pose_data(),
            }
            data = get_next_array(read_character_capture_data)
            return {"type": "MotionCaptureData", "data": data}
        case 2:
            # Sekai_Streaming_SoundData
            channels = get_next_int()
            sample_rate = get_next_int()
            data_length = get_next_int()
            if compress_type != 1:
                data = stream.read(data_length)  # Raw sampling data
                return {
                    "type": "SoundData",
                    "channels": channels,
                    "sampleRate": sample_rate,
                    "encoding": "raw",
                    "data": data,
                }
            else:
                data = stream.read(data_length)  # HCA w/o metadata
                return {
                    "type": "SoundData",
                    "channels": channels,
                    "sampleRate": sample_rate,
                    "encoding": "hca",
                    "data": data,
                }
        case 3:
            # Sekai_Streaming_StatusData
            read_stage_status = lambda: {
                "liveState": get_next_byte(),
                "lightIntensity": get_next_float(),
                "gayaVolume": get_next_float(),
                "cheerVolume": get_next_float(),
                "characterSpotlightIndex": get_next_int(),
                "characterSpotlightIntensity": get_next_float(),
                "stageSetlistIndex": get_next_int(),
                "musicSetlistIndex": get_next_int(),
                "musicTargetTime": get_next_long(),
                "musicStartTime": get_next_float(),
                "seId": get_next_int(),
                "seStartTime": get_next_long(),
                "timeStamp": get_next_long(),
                "unk0": get_next_byte(),
                "unk1": get_next_byte(),
                "playTimelineId": get_next_int(),
                **(
                    {
                        "screenFadeColorR": get_next_byte(),
                        "screenFadeColorG": get_next_byte(),
                        "screenFadeColorB": get_next_byte(),
                        "screenFade": get_next_float(),
                        "characterFormationRotate": get_next_int(),
                        "stageCenterPosition": get_next_vector3(),
                        "playerAvatarStartPosition": get_next_vector3(),
                    }
                    if version >= (1, 4)
                    else {}
                ),
                **(
                    {
                        "characterVisible": get_next_mask(),
                        "eyeLookAtTargetPositionOffset": get_next_vector3(),
                        "eyeLookAtAngleLimit": get_next_vector3(),
                        "isPreloadReverseCharacter": get_next_mask(),
                    }
                    if version >= (1, 5)
                    else {}
                ),
                **(
                    {
                        "eyeLookAtUvLimit": get_next_quaternion(),
                    }
                    if version >= (1, 6)
                    else {}
                ),
                **(
                    {
                        "preloadReserveFirstCharacterDelay": get_next_float(),
                        "preloadReserveCharacterInterval": get_next_float(),
                    }
                    if version >= (1, 7)
                    else {}
                ),
            }
            read_character_status = lambda: {
                "costumeIndex": get_next_int(),
                **({"visible": get_next_mask()} if version >= (1, 6) else {}),
                **({"useFx": get_next_mask()} if version >= (1, 2) else {}),
                "timeStamp": get_next_long(),
            }
            stage_status_list = get_next_array(read_stage_status)
            stage_status_length = get_next_int()
            charcter_status_list = [
                get_next_array(read_character_status)
                for _ in range(stage_status_length)
            ]
            return {
                "type": "StatusData",
                "stageStatus": stage_status_list,
                "characterStatus": charcter_status_list,
            }
        case 4:
            # Sekai_Streaming_VirtualLiveMessageData
            message_id = get_next_int()
            user_id = get_next_string()
            data_length = get_next_int()
            data = stream.read(data_length)
            # CP_BinarySerializer__Deserialize_OtherRoomMessageData
            # CP_BinarySerializer__Deserialize_OtherRoomActionData
            # NOTE: The msgpack payload does not contain the message type
            data = msgpack.unpackb(data)
            return {
                "type": "VirtualLiveMessageData",
                "messageId": message_id,
                "userId": user_id,
                "data": data,
            }
        case 5:
            # Sekai_Streaming_ComplementInfoData
            info_type = get_next_int()
            info_data = get_next_string()
            return {
                "type": "ComplementInfoData",
                "infoType": info_type,
                "infoData": info_data,
            }
    return {"type": "Unknown", "data": buffer}


result = defaultdict(dict)

T = TypeVar("T")


def read_rla_frames(
    reader: Generator[Tuple[T, bytes], None, None], version=(1, 0), strict=True
) -> Generator[Tuple[T, dict], None, None]:
    """Parses a stream of rla fragments and automatically processes split data

    There's NO guarantee that the frames are sorted by the frame ticks.

    Args:
        reader (Generator[Tuple[T, bytes], None, None]): A generator that yields a tuple of timestamp and buffer data
        version (tuple, optional): RLA version, found in respective RLH (JSON) header files. range: see RLA_VERSIONS. Defaults to (1,0).
        strict (bool, optional): If False, incomplete packets will be returned as is. Defaults to True.

    Yields:
        Generator[Tuple[T, dict], None, None]: A generator that yields a tuple of timestamp and parsed frame data. Timestamp format is provided by the reader.
    """
    assert (
        version >= RLA_VERSIONS[0] and version <= RLA_VERSIONS[-1]
    ), "unsupported version"
    __buffers = defaultdict(
        list
    )  # splitIndex:([timestamp, splitInfo, header_signature, data])

    def decode_buffer(header_signature, data):
        decoder_signature, data = decode_buffer_payload(data)
        assert (
            header_signature == decoder_signature
        ), "mismatching signature (header/decoder). packet may be corrupt"
        payload = decode_streaming_data(version, decoder_signature, data, strict)
        return payload

    for timestamp, buffer in reader:
        try:
            split_info, header_signature, data = decode_buffer_base64(buffer)
        except Exception as e:
            if strict:
                raise e
            # Otherwise fail silently
        if split_info:
            splitId, splitIndex, splitNum, dataLength, totalDataLength, base64 = (
                split_info
            )
            __buffers[splitId].append((timestamp, split_info, header_signature, data))
            if len(__buffers[splitId]) == splitNum:
                buffer = b"".join(
                    data
                    for _, _, _, data in sorted(
                        __buffers[splitId], key=lambda x: x[1][1]
                    )  # splitIndex
                )
                if strict:
                    assert len(buffer) == totalDataLength, "incomplete split packet"
                del __buffers[splitId]
                if base64:
                    buffer = b64decode(buffer)
                yield timestamp, decode_buffer(header_signature, buffer)
        else:
            yield timestamp, decode_buffer(header_signature, data)

    if __buffers and strict:
        missing = [(payload[0][0], splitId) for splitId, payload in __buffers.items()]
        raise SSEMissingSplitPacketException(missing)


def read_archive_rla_frames(
    src: BytesIO, version=(1, 0), strict=True
) -> Generator[Tuple[int, dict], None, None]:
    """Parses the Sekai RLA file format used in 'streaming_live/archive' assets.

    The frames are sorted by the frame ticks.

    Args:
        src (BytesIO): Source RLA file stream
        version (tuple, optional): RLA version, found in respective RLH (JSON) header files. range: see RLA_VERSIONS. Defaults to (1,0).
        strict (bool, optional): If False, incomplete packets will be returned as is. Defaults to True.

    Yields:
        Generator[Tuple[int, dict], None, None]: A generator that yields a tuple of timestamp and parsed frame data
    """

    def __packet_gen():
        nonlocal tick

        while tick := read_int(src, 8):
            if tick:
                buffer_length = read_int(src, 4)
                buffer = src.read(buffer_length)
                yield tick, buffer

    packets = __packet_gen()
    for tick, frame in read_rla_frames(packets, version, strict):
        yield tick, frame
