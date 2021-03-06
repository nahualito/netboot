from typing import List, Optional, Tuple, cast


class BinaryException(Exception):
    pass


class Binary:

    CHUNK_SIZE = 1024

    @staticmethod
    def _hex(val: int) -> str:
        out = hex(val)[2:]
        out = out.upper()
        if len(out) == 1:
            out = "0" + out
        return out

    @staticmethod
    def diff(bin1: bytes, bin2: bytes) -> List[str]:
        binlength = len(bin1)
        if binlength != len(bin2):
            raise BinaryException("Cannot diff different-sized binary blobs!")

        # First, get the list of differences
        differences: List[Tuple[int, bytes, bytes]] = []

        # Chunk the differences, assuming files are usually about the same,
        # for a massive speed boost.
        for offset in range(0, binlength, Binary.CHUNK_SIZE):
            if bin1[offset:(offset + Binary.CHUNK_SIZE)] != bin2[offset:(offset + Binary.CHUNK_SIZE)]:
                for i in range(Binary.CHUNK_SIZE):
                    byte1 = bin1[offset + i]
                    byte2 = bin2[offset + i]

                    if byte1 != byte2:
                        differences.append((offset + i, bytes([byte1]), bytes([byte2])))

        # Don't bother with any combination crap if we have nothing to do
        if not differences:
            return []

        # Now, combine them for easier printing
        cur_block: Tuple[int, bytes, bytes] = differences[0]
        ret: List[str] = []

        # Now, include the original byte size for later comparison/checks
        ret.append(f"# File size: {len(bin1)}")

        def _hexrun(val: bytes) -> str:
            return " ".join(Binary._hex(v) for v in val)

        def _output(val: Tuple[int, bytes, bytes]) -> None:
            start = val[0] - len(val[1]) + 1

            ret.append(
                f"{Binary._hex(start)}: {_hexrun(val[1])} -> {_hexrun(val[2])}"
            )

        def _combine(val: Tuple[int, bytes, bytes]) -> None:
            nonlocal cur_block

            if cur_block[0] + 1 == val[0]:
                # This is a continuation of a run
                cur_block = (
                    val[0],
                    cur_block[1] + val[1],
                    cur_block[2] + val[2],
                )
            else:
                # This is a new run
                _output(cur_block)
                cur_block = val

        # Combine and output runs of differences
        for diff in differences[1:]:
            _combine(diff)

        # Make sure we output the last difference
        _output(cur_block)

        # Return our summation
        return ret

    @staticmethod
    def size(patchlines: List[str]) -> Optional[int]:
        for patch in patchlines:
            if patch.startswith('#'):
                # This is a comment, ignore it, unless its a file-size comment
                patch = patch[1:].strip().lower()
                if patch.startswith('file size:'):
                    return int(patch[10:].strip())
        return None

    @staticmethod
    def _convert(val: str) -> Optional[int]:
        val = val.strip()
        if val == '*':
            return None
        return int(val, 16)

    @staticmethod
    def _gather_differences(patchlines: List[str], reverse: bool) -> List[Tuple[int, Optional[bytes], bytes]]:
        # First, separate out into a list of offsets and old/new bytes
        differences: List[Tuple[int, Optional[bytes], bytes]] = []

        for patch in patchlines:
            if patch.startswith('#'):
                # This is a comment, ignore it.
                continue
            start_offset, patch_contents = patch.split(':', 1)
            before, after = patch_contents.split('->')
            beforevals = [
                Binary._convert(x) for x in before.split(" ") if x.strip()
            ]
            aftervals = [
                Binary._convert(x) for x in after.split(" ") if x.strip()
            ]

            if len(beforevals) != len(aftervals):
                raise BinaryException(
                    f"Patch before and after length mismatch at "
                    f"offset {start_offset}!"
                )
            if len(beforevals) == 0:
                raise BinaryException(
                    f"Must have at least one byte to change at "
                    f"offset {start_offset}!"
                )

            offset = int(start_offset.strip(), 16)

            for i in range(len(beforevals)):
                if aftervals[i] is None:
                    raise BinaryException(
                        f"Cannot convert a location to a wildcard "
                        f"at offset {start_offset}"
                    )
                if beforevals[i] is None and reverse:
                    raise BinaryException(
                        f"Patch offset {start_offset} specifies a wildcard and cannot "
                        f"be reversed!"
                    )
                differences.append(
                    (
                        offset + i,
                        bytes([beforevals[i] or 0]) if beforevals[i] is not None else None,
                        bytes([aftervals[i] or 0]),
                    )
                )

        # Now, if we're doing the reverse, just switch them
        if reverse:
            # We cast here because mypy can't see that we have already asserted that x[2] will never
            # be optional in the above loop if reverse is set to True.
            differences = [cast(Tuple[int, Optional[bytes], bytes], (x[0], x[2], x[1])) for x in differences]

        # Finally, return it
        return differences

    @staticmethod
    def patch(
        binary: bytes,
        patchlines: List[str],
        *,
        reverse: bool = False,
    ) -> bytes:
        # First, grab the differences
        file_size = Binary.size(patchlines)
        if file_size is not None and file_size != len(binary):
            raise BinaryException(
                f"Patch is for binary of size {file_size} but binary is {len(binary)} "
                f"bytes long!"
            )
        differences: List[Tuple[int, Optional[bytes], bytes]] = sorted(
            Binary._gather_differences(patchlines, reverse),
            key=lambda diff: diff[0],
        )
        chunks: List[bytes] = []
        last_patch_end: int = 0

        # Now, apply the changes to the binary data
        for diff in differences:
            offset, old, new = diff

            if len(binary) < offset:
                raise BinaryException(
                    f"Patch offset {Binary._hex(offset)} is beyond the end of "
                    f"the binary!"
                )
            if old is not None and binary[offset:(offset + 1)] != old:
                raise BinaryException(
                    f"Patch offset {Binary._hex(offset)} expecting {Binary._hex(old[0])} "
                    f"but found {Binary._hex(binary[offset])}!"
                )

            if last_patch_end < offset:
                chunks.append(binary[last_patch_end:offset])
            chunks.append(new)
            last_patch_end = offset + 1

        # Return the new data!
        chunks.append(binary[last_patch_end:])
        return b"".join(chunks)

    @staticmethod
    def can_patch(
        binary: bytes,
        patchlines: List[str],
        *,
        reverse: bool = False,
        ignore_size_differences: bool = False,
    ) -> Tuple[bool, str]:
        # First, grab the differences
        if not ignore_size_differences:
            file_size = Binary.size(patchlines)
            if file_size is not None and file_size != len(binary):
                return (
                    False,
                    f"Patch is for binary of size {file_size} but binary is {len(binary)} "
                    f"bytes long!"
                )
        differences: List[Tuple[int, Optional[bytes], bytes]] = Binary._gather_differences(patchlines, reverse)

        # Now, verify the changes to the binary data
        for diff in differences:
            offset, old, _ = diff

            if len(binary) < offset:
                return (
                    False,
                    f"Patch offset {Binary._hex(offset)} is beyond the end of "
                    f"the binary!"
                )
            if old is not None and binary[offset:(offset + 1)] != old:
                return (
                    False,
                    f"Patch offset {Binary._hex(offset)} expecting {Binary._hex(old[0])} "
                    f"but found {Binary._hex(binary[offset])}!"
                )

        # Didn't find any problems
        return (True, "")

    @staticmethod
    def description(patchlines: List[str]) -> Optional[str]:
        for patch in patchlines:
            if patch.startswith('#'):
                # This is a comment, ignore it, unless its a description comment
                patch = patch[1:].strip().lower()
                if patch.startswith('description:'):
                    return patch[12:].strip()
        return None

    @staticmethod
    def needed_amount(patchlines: List[str]) -> int:
        # First, grab the differences.
        differences: List[Tuple[int, Optional[bytes], bytes]] = Binary._gather_differences(patchlines, False)

        # Now, get the maximum byte we need to apply this patch.
        return max([offset for offset, _, _ in differences]) + 1 if differences else 0
