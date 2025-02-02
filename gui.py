#! python3
import sys
import argparse
import threading
import subprocess
import urllib.request
import functools
import io
import os
import time
import tkinter as tk
import PIL
# import PIL.Image
# import PIL.ImageTk
import mutagen.mp3
from mutagen.id3 import APIC

from itunesart import findAlbumArt
from PIL import Image
from PIL import ImageTk


class Gui(tk.Tk):
    _imageRefs = {}

    def __init__(self, args, files):
        super().__init__()

        self.args = args
        self.files = files

        self.bind('<Escape>', self.close)
        self.bind('<Return>', functools.partial(self.search, query=None))

        self.title("iTunes Art Downloader")

        self.imageSize = 250
        self.downloadSize = 1000
        self.autocloseinseconds = 3

        self._resultWidgets = []

        frame = tk.Frame(self)

        tk.Label(frame, text='Query:').pack(padx=0, pady=2, side=tk.LEFT)
        self.entry = tk.Entry(frame, textvariable=tk.StringVar(""), width=40)
        self.entry.pack(padx=2, pady=2, side=tk.LEFT)
        tk.Button(
            frame,
            text="Go",
            command=self.search).pack(
            padx=2,
            pady=2,
            side=tk.LEFT)

        frame.pack(fill=tk.X)

    def close(self, event=None):
        self.withdraw()
        sys.exit()

    def autoclose(self, event=None):
        time.sleep(self.autocloseinseconds)
        self.close()

    def _loadImage(self, widget, url):
        raw_data = urllib.request.urlopen(url).read()
        im = PIL.Image.open(io.BytesIO(raw_data))
        Gui._imageRefs[url] = PIL.ImageTk.PhotoImage(im)
        widget.configure(image=Gui._imageRefs[url])

    def search(self, event=None, query=None):
        if query is None:
            query = self.entry.get()

        if not query or not query.strip():
            return

        self.entry.delete(0, 'end')
        self.entry.insert(0, query)

        for w in self._resultWidgets:
            w.pack_forget()
        self._resultWidgets = []

        itemsPerRow = int(self.winfo_screenwidth() / (self.imageSize + 10))
        maxRows = int(self.winfo_screenheight() / (self.imageSize + 10))

        searchResults = findAlbumArt(
            query, dimensions=(
                self.imageSize, self.imageSize, 'bb'))

        row = None

        if not searchResults:
            row = tk.Frame(self)
            self._resultWidgets.append(row)
            row.pack(fill=tk.X)
            label = tk.Label(row, text="No results.")
            label.pack(fill=tk.X)

        for i, result in enumerate(searchResults):
            if i % itemsPerRow == 0:
                row = tk.Frame(self)
                self._resultWidgets.append(row)
                row.pack(fill=tk.X)
            if len(self._resultWidgets) > maxRows:
                continue

            frame = tk.Frame(row)
            frame.pack(padx=2, pady=2, side=tk.LEFT)
            url = result['image']

            title = '%s - %s' % (result["artist"], result["name"])
            if len(title) > 55:
                title = result["artist"][0:25]
                title += "-" + result["name"][0:55 - len(title)]
            label = tk.Label(frame, text=title)
            label.pack(fill=tk.X)

            if not url in Gui._imageRefs:
                Gui._imageRefs[url] = None

            button = tk.Button(
                frame,
                image=Gui._imageRefs[url],
                command=functools.partial(
                    self.selectedImage,
                    result))
            button.pack(fill=tk.X)

            if Gui._imageRefs[url] is None:
                t = threading.Thread(target=self._loadImage, args=(button, url))
                t.daemon = True
                t.start()


    def selectedImage(self, result):
        if not self.files:
            print("No files found")
            self.entry.delete(0, 'end')
            self.entry.insert(0, "No files found")
            return
    
        url = result['image'].replace(
            "%dx%dbb.jpg" %
            (self.imageSize, self.imageSize), "%dx%dbb.jpg" %
            (self.downloadSize, self.downloadSize))
        artwork = False
        if self.args.isAlbum:
            dirname = os.path.dirname(self.files[0])
            folderjpg = os.path.join(dirname, 'folder.jpg')
            newfolderjpg = os.path.join(dirname, '_newfolder.jpg')
            
            urllib.request.urlretrieve(url, newfolderjpg)
            if os.path.exists(newfolderjpg):
                try:
                    if os.path.exists(folderjpg):
                        os.remove(folderjpg)
                except:
                    try:
                        subprocess.check_call(
                            ["attrib", "-H", "-R", folderjpg])
                        os.remove(folderjpg)
                    except:
                        os.remove(newfolderjpg)
                if not os.path.exists(folderjpg):
                    os.rename(newfolderjpg, folderjpg)
                    subprocess.check_call(["attrib", "+H", "+R", folderjpg])
            if os.path.exists(folderjpg):
                artwork = open(folderjpg, 'rb').read()

        if not artwork:
            artwork = urllib.request.urlopen(url).read()

        if not artwork:
            print("Could not download artwork")
            self.entry.delete(0, 'end')
            self.entry.insert(0, "Could not download artwork")
            return

        i = 0
        for filename in self.files:
            try:
                audio = mutagen.mp3.MP3(filename)
            except:
                print("Could not open file: %s" % str(filename))
                continue
            audio.tags.add(
                APIC(
                    encoding=3,  # 3 is for utf-8
                    mime='image/jpeg',  # image/jpeg or image/png
                    type=3,  # 3 is for the cover image
                    desc=u'',
                    data=artwork
                )
            )
            try:
                audio.save()
            except:
                print("Could not save file: %s" % str(filename))
                continue

            i += 1

        status = "Saved %d/%d files!" % (i, len(self.files))
        if i == len(self.files):
            status += ' Closing...'

        self.entry.delete(0, 'end')
        self.entry.insert(0, status)
        print(status)

        if i == len(self.files):
            return self.autoclose()

    def __repr__(self):
        return "GuiObject()"

    def __str__(self):
        return "GuiObject()"


def main(args):
    print(args.isAlbum)
    print(args.query)
    print(args.filename)

    if os.path.exists(args.filename):
        if os.path.isdir(args.filename) and not args.isAlbum:
            print(
                "Filename is a folder but album mode not enabled. Use -a for album mode.")
            return 1

    else:
        print("Filename is not a valid path: %s" % (args.filename,))
        return 2

    if args.isAlbum:
        print("++++Album Mode++++")
        dirname = os.path.dirname(
            os.path.abspath(
                args.filename)) if os.path.isfile(
            args.filename) else os.path.abspath(
                args.filename)
        mp3s = []
        walk = os.walk(dirname)
        for root, dirs, files in walk:
            for name in files:
                if name.lower().endswith('.mp3'):
                    mp3s.append(os.path.join(root, name))
                    print(" *", name)
    else:
        mp3s = [os.path.abspath(args.filename), ]

    query = ""
    if args.query:
        query = args.query
    else:
        # Read id3 data
        try:
            audio = mutagen.mp3.MP3(mp3s[0])
            query = ""
            if "TALB" in audio and str(audio["TALB"]):
                query += " " + str(audio["TALB"])
            elif "TIT2" in audio and str(audio["TIT2"]):
                query += " " + str(audio["TIT2"])
            if "TPE2" in audio and str(audio["TPE2"]):
                query += " " + str(audio["TPE2"])
            elif "TPE1" in audio and str(audio["TPE1"]):
                query += " " + str(audio["TPE1"])
            query = query.strip()
        except e:
            print("Could not read ID3 data:")
            print(e)

    print("Query=%s" % query)

    gui = Gui(args, files=mp3s)
    gui.search(query=query)
    gui.mainloop()


if __name__ == "__main__":
    # Arguments
    parser = argparse.ArgumentParser(
        description='Add cover from iTunes Store to an album or single file')
    parser.add_argument(
        '-a',
        dest='isAlbum',
        action='store_const',
        const=True,
        default=False,
        help='Album mode, store cover in all files in this directory')

    parser.add_argument(
        '-q',
        dest='query',
        help='Search with this query instead of artist/tile from id3 metadata from the mp3 file')

    parser.add_argument(
        'filename',
        nargs='?',
        help='A mp3 file or folder with multiple mp3 files')

    args = parser.parse_args()

    main(args)
