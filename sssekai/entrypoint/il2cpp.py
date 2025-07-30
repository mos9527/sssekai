import logging, os, shutil

logger = logging.getLogger(__name__)


METADATA_MAGIC = b"\xaf\x1b\xb1\xfa"
SIG_DW_OP_piece = b"DW_OP_piece not implemented\x00x5\x00x10\x00"


def main_il2cpp(args):
    try:
        import lief
    except ImportError as e:
        logger.error(
            "Please install sssekai[il2cpp] through your Python package manager to use the il2cpp entrypoint"
        )
        raise e
    logger.info("Loading metadata from %s", args.metadata)
    metadata = bytearray(open(args.metadata, "rb").read())
    assert (
        metadata[:4] != METADATA_MAGIC
    ), "Metadata file is unlikely to be protected with XOR cipher (non-obfuscated header)"
    logger.info("Loading binary from %s", args.binary)
    elf = lief.ELF.parse(args.binary)
    text: lief.ELF.Section = elf.get_section(".rodata")
    text = text.content.tobytes()
    # Yes - the heuristic is *that* simple.
    # We're probably fine if Unity never changes their bundled NDK for JP
    # Verified to work with JP 3.8.1 & 5.5.0
    off = text.find(SIG_DW_OP_piece)
    assert (
        off != -1
    ), "Signature not found in the binary. NOTE: Only JP Android releases are verified and supported."
    off += len(SIG_DW_OP_piece)
    key = text[off : off + 0x80]
    logger.info("Key: %s", key.hex())
    for i in range(0, len(metadata)):
        metadata[i] ^= key[i & 0x7F]
        if i == 4:
            assert metadata[:4] == METADATA_MAGIC, "Metadata deobfuscation failed"
    logger.info("Metadata seems OK. Saving files to %s", args.outdir)
    os.makedirs(args.outdir, exist_ok=True)
    with open(os.path.join(args.outdir, "global-metadata.dat"), "wb") as f:
        f.write(metadata)
    shutil.copy(args.binary, os.path.join(args.outdir, "il2cpp.so"))
