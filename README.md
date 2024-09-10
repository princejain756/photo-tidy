# photo-tidy

`photo-tidy` sorts a messy folder of photos into `YYYY/MM` folders using the
capture date stored in each file's EXIF data. It reports what it would do
before touching anything, keeps a journal of every move, and can undo the
last run.

```
$ photo-tidy ~/Pictures/import
move   import/IMG_1042.jpg -> 2019/03/IMG_1042.jpg
move   import/IMG_2014.jpg -> 2020/12/IMG_2014.jpg
skip   import/scan.jpg (no capture date)

2 to move, 1 skipped
```

Nothing moves until you pass `--run`.

## Install

```
pip install .
```

Or run the checkout directly without installing:

```
python3 photo_tidy.py --help
```

Python 3.8 or newer. The core logic is standard library only.

## Usage

```
photo-tidy DIRECTORY [options]
```

| Option | Effect |
| --- | --- |
| `--run` | Actually move the files. Without it the run is a dry run. |
| `--duplicates` | Report byte-identical files and move only one copy. |
| `--mtime` | Fall back to the file modification time when a photo has no EXIF date. |
| `--ext EXT` | Treat an extra extension as a photo, e.g. `--ext cr2`. Repeatable. |
| `--undo` | Move the files from the last run back where they came from. |
| `--version` | Print the version. |

### Dry run first

A plain run only prints the plan:

```
photo-tidy ~/Pictures/import
```

Check the plan, then repeat the command with `--run`.

### Undo

Every run writes a journal to `DIRECTORY/.phototidy/`. To reverse the most
recent run:

```
photo-tidy ~/Pictures/import --undo
```

Undo replays the newest journal backwards and removes year/month folders it
emptied. Journals are kept so that older runs stay reversible; delete the
`.phototidy` folder once you are happy with the result.

## What counts as a photo

By default: `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.png`. Add formats with `--ext`.
Only the date is read from EXIF, never anything else, and nothing leaves your
machine.

Files without a readable capture date are skipped and listed with a reason.
Pass `--mtime` to file those by modification time instead.

## Duplicates

`--duplicates` hashes file contents with SHA-256 and reports identical files.
The oldest capture wins and the later copies are left where they are, so you
can review them before deleting anything.

```
$ photo-tidy ~/Pictures/import --duplicates
dup    import/IMG_1042.jpg = import/IMG_1042-copy.jpg
move   import/IMG_1042.jpg -> 2019/03/IMG_1042.jpg
skip   import/IMG_1042-copy.jpg (duplicate of IMG_1042.jpg)
```

## Development

```
make test    # the test suite
make lint    # pycodestyle over the package and the tests
make all     # both of the above
```

The suite needs only `pytest`; `lint` needs `pycodestyle`.

## Layout

| Path | Contents |
| --- | --- |
| `phototidy/exif.py` | JPEG segment walk and EXIF date parsing |
| `phototidy/plan.py` | Plans moves and resolves collisions |
| `phototidy/hashes.py` | Content hashing for duplicate detection |
| `phototidy/run.py` | Executes a plan and writes the undo journal |
| `phototidy/cli.py` | Argument parsing and reporting |

## Limitations

- Only JPEG EXIF is read. PNG and TIFF files need `--mtime`.
- A photo whose date cannot be parsed is skipped, never guessed.
- Moves cross filesystems via a copy, which doubles the space needed briefly.

## License

MIT. See `LICENSE`.
