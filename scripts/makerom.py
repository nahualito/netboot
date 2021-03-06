#! /usr/bin/env python3
import argparse
import datetime
import sys
from typing import List

from naomi import NaomiRom, NaomiExecutable, NaomiRomSection


def main() -> int:
    # Create the argument parser
    parser = argparse.ArgumentParser(
        description="Utility for creating a Naomi ROM out of various parameters and sections.",
    )
    parser.add_argument(
        'bin',
        metavar='BIN',
        type=str,
        help='The binary file we should generate.',
    )
    parser.add_argument(
        '-s',
        '--serial',
        type=str,
        default=None,
        help='Three digit ascii serial code for this game.',
    )
    parser.add_argument(
        '-p',
        '--publisher',
        type=str,
        default=None,
        help='The publisher of this ROM.',
    )
    parser.add_argument(
        '-t',
        '--title',
        type=str,
        default=None,
        help=(
            'The name of this ROM. Use this instead of individual ROM region titles '
            'to globally set the name of the ROM.'
        ),
    )
    parser.add_argument(
        '--title.japan',
        dest="title_japan",
        type=str,
        default=None,
        help='The name of this ROM in Japanese region.',
    )
    parser.add_argument(
        '--title.usa',
        dest="title_usa",
        type=str,
        default=None,
        help='The name of this ROM in USA region.',
    )
    parser.add_argument(
        '--title.export',
        dest="title_export",
        type=str,
        default=None,
        help='The name of this ROM in Export region.',
    )
    parser.add_argument(
        '--title.korea',
        dest="title_korea",
        type=str,
        default=None,
        help='The name of this ROM in Korea region.',
    )
    parser.add_argument(
        '--title.australia',
        dest="title_australia",
        type=str,
        default=None,
        help='The name of this ROM in Australia region.',
    )
    parser.add_argument(
        '-d',
        '--date',
        type=str,
        default=None,
        help='The date this ROM was created, in the form YYYY-MM-DD',
    )
    parser.add_argument(
        '-e',
        '--entrypoint',
        type=str,
        required=True,
        help='The executable entrypoint in main RAM after loading all sections.',
    )
    parser.add_argument(
        '-c',
        '--section',
        type=str,
        action='append',
        help=(
            'An executable section that will be loaded into RAM. Must be specified '
            'in the form of /path/to/file,0x12345678 where the hexidecimal number is '
            'the load offset in main RAM.'
        )
    )
    parser.add_argument(
        '-n',
        '--test-entrypoint',
        type=str,
        required=True,
        help='The test mode entrypoint in main RAM after loading all sections.',
    )
    parser.add_argument(
        '-i',
        '--test-section',
        type=str,
        action='append',
        help=(
            'A test mode section that will be loaded into RAM. Must be specified '
            'in the form of /path/to/file,0x12345678 where the hexidecimal number is '
            'the load offset in main RAM.'
        )
    )
    parser.add_argument(
        '-b',
        '--pad-before-data',
        type=str,
        default=None,
        help='Pad the ROM to this size in hex before appending any arbitrary data.',
    )
    parser.add_argument(
        '-a',
        '--pad-after-data',
        type=str,
        default=None,
        help='Pad the ROM to this size in hex after appending any arbitrary data.',
    )
    parser.add_argument(
        '-f',
        '--filedata',
        metavar="FILE",
        type=str,
        action='append',
        help='Append this arbitrary file data to the end of the ROM.',
    )

    # Grab what we're doing
    args = parser.parse_args()

    # Create the ROM header itself
    header = NaomiRom.default()

    # Start by attaching basic info
    header.publisher = args.publisher or "NOBODY"
    title = [
        args.title or "NO TITLE",
        args.title or "NO TITLE",
        args.title or "NO TITLE",
        args.title or "NO TITLE",
        args.title or "NO TITLE",
    ]
    if args.title_japan:
        title[header.REGION_JAPAN] = args.title_japan
    if args.title_usa:
        title[header.REGION_JAPAN] = args.title_usa
    if args.title_export:
        title[header.REGION_JAPAN] = args.title_export
    if args.title_korea:
        title[header.REGION_JAPAN] = args.title_korea
    if args.title_australia:
        title[header.REGION_JAPAN] = args.title_australia
    header.names = title

    # I am not sure whether anyone will want to overwrite these
    header.sequencetexts = [
        "CREDIT TO START",
        "CREDIT TO CONTINUE",
    ]
    header.regions = [
        header.REGION_JAPAN,
        header.REGION_USA,
        header.REGION_EXPORT,
        header.REGION_KOREA,
        header.REGION_AUSTRALIA,
    ]

    if args.date is not None:
        year, month, day = args.date.split('-')
        header.date = datetime.date(int(year), int(month), int(day))
    else:
        header.date = datetime.date.today()

    if args.serial is not None:
        if len(args.serial) != 3:
            raise Exception("Serial must be 3 ascii digits!")
        header.serial = b"B" + args.serial.encode('ascii')
    else:
        header.serial = b"B999"

    # TODO: Command line args for setting supported number of players,
    # screen orientation, coin service type, supported monitor frequencies,
    # and defaults for various EEPROM settings such as free-play.

    # Construct executable and test loader sections.
    main_sections: List[NaomiRomSection] = []
    test_sections: List[NaomiRomSection] = []
    romoffset = len(header.data)
    romdata = b''

    # Calculate locations for appended executable chunks.
    for file_and_offset in args.section or []:
        filename, offset = file_and_offset.rsplit(',', 1)
        with open(filename, "rb") as fpb:
            sectiondata = fpb.read()

        main_sections.append(
            NaomiRomSection(
                offset=romoffset,
                length=len(sectiondata),
                load_address=int(offset, 16),
            )
        )
        romoffset += len(sectiondata)
        romdata += sectiondata

    # Calculate locations for appended test mode chunks.
    for file_and_offset in args.test_section or []:
        filename, offset = file_and_offset.rsplit(',', 1)
        with open(filename, "rb") as fpb:
            sectiondata = fpb.read()

        test_sections.append(
            NaomiRomSection(
                offset=romoffset,
                length=len(sectiondata),
                load_address=int(offset, 16),
            )
        )
        romoffset += len(sectiondata)
        romdata += sectiondata

    # Create the executable itself.
    header.main_executable = NaomiExecutable(
        sections=main_sections,
        entrypoint=int(args.entrypoint, 16)
    )
    header.test_executable = NaomiExecutable(
        sections=test_sections,
        entrypoint=int(args.test_entrypoint, 16)
    )

    # Now, pad the ROM out to any requested padding.
    if args.pad_before_data and romoffset < int(args.pad_before_data, 16):
        amount = int(args.pad_before_data, 16) - romoffset
        romdata += b'\0' * amount
        romoffset += amount

    # Now, append any requested data chunks.
    for filename in args.filedata or []:
        with open(filename, "rb") as fpb:
            filedata = fpb.read()
        romoffset += len(filedata)
        romdata += filedata

    # Now, pad the ROM out to any requested padding.
    if args.pad_after_data and romoffset < int(args.pad_after_data, 16):
        amount = int(args.pad_after_data, 16) - romoffset
        romdata += b'\0' * amount
        romoffset += amount

    # Finally, write out the pieces
    with open(args.bin, "wb") as fpb:
        fpb.write(header.data)
        fpb.write(romdata)

    return 0


if __name__ == "__main__":
    sys.exit(main())
