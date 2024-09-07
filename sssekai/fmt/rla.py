from base64 import b64decode, b64encode
from struct import unpack as s_unpack
from io import BytesIO
from collections import defaultdict
import math, gzip
import msgpack

read_int = lambda stream, nbytes, signed=False: int.from_bytes(stream.read(nbytes), 'little',signed=signed)
read_float = lambda stream: s_unpack('<f', stream.read(4))[0]
# Sekai_Streaming_StreamingCommon__CheckHeader
def decode_buffer_base64(buffer):
    is_base64_encoded = buffer[6 + 4 + 4]
    is_split = buffer[6 + 4 + 1 + 3]
    data = buffer[6 + 4 + 1 + 4:]
    if is_base64_encoded:
        data = b64decode(data)
    return data
# Sekai_Streaming_SubscribeDecoder__Deserialize
def decode_buffer_payload(buffer):        
    stream = BytesIO(buffer)
    decoder_type = read_int(stream, 1)
    unk1 = read_int(stream, 4)
    if not unk1:
        unk2 = read_int(stream, 4)
        if unk2:
            payload = stream.read()
            payload = gzip.decompress(payload)
            return decoder_type, payload        
    return decoder_type, stream.read()
# Sekai_Streaming_StreamingData__Deserialize
def decode_streaming_data(version, decoder_type, buffer):
    stream = BytesIO(buffer)
    n_mask_offset = read_int(stream, 4)
    n_init_pos = stream.tell()
    stream.seek(n_mask_offset)
    n_mask_length = read_int(stream, 2)
    bitmask = stream.read(n_mask_length)
    assert not stream.read() # EOF
    stream.seek(n_init_pos)
    # CP_Serialize_SerializableValueSet
    bitmask = [bitmask[i // 8] & (1 << (i % 8)) != 0 for i in range(len(bitmask) * 8)]
    get_next_mask = lambda: bitmask.pop(0) # GetNextMask, ReadBool
    get_next_pred = lambda: get_next_mask() | (get_next_mask() << 1)
    get_next_byte = lambda: [lambda: 0, lambda: 1, lambda: -1, lambda: read_int(stream, 1)][get_next_pred()]() # ReadByte
    get_next_ushort = lambda: [lambda: 0.0, lambda: 0.0, lambda: read_int(stream, 1), lambda: read_int(stream, 2)][get_next_pred()]() # ReadUShort
    get_next_short =  lambda: [lambda: 0.0, lambda: 0.0, lambda: read_int(stream, 1, True), lambda: read_int(stream, 2)][get_next_pred()]() # ReadShort
    get_next_int = lambda: [lambda: 0, lambda: read_int(stream,1), lambda: read_int(stream,1,True), lambda: read_int(stream, 4)][get_next_pred()]() # ReadInt
    get_next_long = lambda: [lambda: 0, lambda: read_int(stream,1), lambda: read_int(stream,2), lambda: read_int(stream, 8)][get_next_pred()]() # ReadLong
    get_next_float = lambda: [lambda: 0.0, lambda: 0.0, lambda: 3.4028e38, lambda: read_float(stream)][get_next_pred()]() # ReadSingle
    get_next_vector3 = lambda: (get_next_float(), get_next_float(), get_next_float()) # ReadVector3
    get_next_ushort_vector3 = lambda: (get_next_ushort() * 0.01, get_next_ushort() * 0.01, get_next_ushort() * 0.01) # ReadUShortVector3
    get_next_tiny_int = lambda type: {'+': lambda: read_int(stream, 2), '*': lambda: read_int(stream, 1, True), ')': lambda: read_int(stream, 1)}[type]() # ReadTinyInt
    get_next_string = lambda: stream.read(get_next_tiny_int(chr(read_int(stream, 1)))).decode() if get_next_pred() else None # ReadString
    get_next_array = lambda reader: [reader() for _ in range(get_next_int())]  # ReadArray<T>
    # Sekai_Streaming_StreamingData__Deserialize
    assert get_next_byte() == decoder_type
    compress_type = get_next_int()
    sequence_no = get_next_int()
    target_time = get_next_long()
    # StreamingData$$ReadValue implementations
    deg_to_rad = lambda value: tuple(deg * (math.pi / 180) for deg in value)
    get_next_deg_as_rad = lambda: deg_to_rad(get_next_ushort_vector3()) # Eulers [0, 2pi]
    get_next_pose_data = lambda: {
        'bodyPosition': get_next_vector3(),
        'bodyRotation': get_next_deg_as_rad(), # Eulers
        **({
            'musicItemPropPosition': get_next_vector3(),
            'musicItemPropRotation': get_next_deg_as_rad()
        } if version >= (1,1) else {}),                    
        'boneDatas': get_next_array(get_next_deg_as_rad), # Eulers [0, 2pi]
        'shapeDatas': get_next_array(get_next_float), # [0,100]
        **({
            'propBoneDatas': get_next_array(get_next_deg_as_rad) # Eulers [0, 2pi]
        } if version >= (1,1) else {}),
        'heightOffset': get_next_short() * 0.01,
        'isActive': get_next_mask(),
        'useActiveFx': get_next_mask(),
        **({
            'isEyeLookAt': get_next_mask()
        } if version >= (1,4) else {})
    }
    match decoder_type:
        case 0:
            # Sekai_Streaming_MotionData
            timeStamps = get_next_array(get_next_long) if get_next_pred() == 2 else None
            poses = get_next_array(get_next_pose_data)
            return {'type': 'MotionData', 'timeStamps': timeStamps, 'poses': poses}
        case 1:
            # Sekai_Streaming_MotionCaptureData
            read_character_capture_data = lambda: {
                'id': get_next_int(),
                'timestamp': get_next_long(),
                'pose': get_next_pose_data()
            }
            data = get_next_array(read_character_capture_data)
            return {'type': 'MotionCaptureData', 'data': data}
        case 2:
            # Sekai_Streaming_SoundData
            channels = get_next_int()
            sample_rate = get_next_int()
            data_length = get_next_int()
            if compress_type != 1:
                data = stream.read(data_length) # Raw sampling data
                return {'type': 'SoundData', 'channels': channels, 'sampleRate': sample_rate, 'encoding': 'raw', 'data': b64encode(data).decode()}
            else:
                data = stream.read(data_length) # HCA w/o metadata
                return {'type': 'SoundData', 'channels': channels, 'sampleRate': sample_rate, 'encoding': 'hca', 'data': b64encode(data).decode()}              
        case 3:
            # Sekai_Streaming_StatusData
            read_stage_status = lambda: {
                'liveState': get_next_byte(),
                'lightIntensity': get_next_float(),
                'gayaVolume': get_next_float(),
                'cheerVolume': get_next_float(),
                'characterSpotlightIndex': get_next_int(),
                'characterSpotlightIntensity': get_next_float(),
                'stageSetlistIndex': get_next_int(),
                'musicSetlistIndex': get_next_int(),
                'musicTargetTime': get_next_long(),
                'musicStartTime': get_next_float(),
                'seId': get_next_int(),
                'seStartTime': get_next_long(),
                'timeStamp': get_next_long(),
                'unk0': get_next_byte(),
                'unk1': get_next_byte(),
                'playTimelineId': get_next_int(),                    
                ** ({
                    'screenFadeColorR': get_next_byte(),
                    'screenFadeColorG': get_next_byte(),
                    'screenFadeColorB': get_next_byte(),
                    'screenFade': get_next_float(),
                    'characterFormationRotate': get_next_int(),
                    'stageCenterPosition': get_next_vector3(),
                    'playerAvatarStartPosition': get_next_vector3()
                } if version >= (1,4) else {})
            }
            read_character_status = lambda: {
                'costumeIndex': get_next_int(),
                ** ({'useFx': get_next_mask()} if version >= (1,2) else {}),
                'timeStamp': get_next_long(),
            }
            stage_status_list = get_next_array(read_stage_status)
            stage_status_length = get_next_int()                
            charcter_status_list = [get_next_array(read_character_status) for _ in range(stage_status_length)]
            return {'type': 'StatusData', 'stageStatus': stage_status_list, 'characterStatus': charcter_status_list}
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
            return {'type': 'VirtualLiveMessageData','messageId': message_id, 'userId': user_id, 'data': data}
        case 5:
            # Sekai_Streaming_ComplementInfoData
            info_type = get_next_int()
            info_data = get_next_string()
            return {'type': 'ComplementInfoData', 'infoType': info_type, 'infoData': info_data}            
    return {'type': 'Unknown', 'data': buffer}
result = defaultdict(dict)

def read_rla(src : BytesIO, version=(1,0)) -> dict:
    '''Parses the Sekai RLA file format used in 'streaming_live/archive' assets.

    Args:
        src (BytesIO): Source RLA file stream
        version (tuple, optional): RLA version, found in respective RLH (JSON) header files. Defaults to (1,0).

    Returns:
        dict: Parsed RLA data. The dictionary is sorted by the frame ticks.
    '''    
    def read_frames():
        ticks = read_int(src, 8)
        if ticks:
            buffer_length = read_int(src, 4)
            buffer = src.read(buffer_length)
            # [RTVL... (15 bytes)][data]
            data = decode_buffer_base64(buffer)
            decoder_type, data = decode_buffer_payload(data)
            data = decode_streaming_data(version, decoder_type, data)
            result[ticks].setdefault(data['type'], list()).append(data)
            return True
        return False
    while read_frames(): pass        
    result = dict(sorted(result.items(), key=lambda x: x[0]))
    return result

if __name__ == '__main__':
    result = read_rla(open(r"D:\project\TextAsset\sekai_30_00000000.rla.bytes",'rb'), (1,0))
    pass