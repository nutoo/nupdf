#!/usr/bin/env python
#
# Copyright (C) 2011 Christoph Lehner, Nathan Goldschmidt
#
#    v1[Lehner]:      Original version
#    v2[Goldschmidt]: Use expanduser, expandvars.  Use self.fn instead of fn.
#    v3[Lehner]:      Use self.fn in argument of exportPdf.
#
# All programs in this directory and subdirectories are published under the GNU
# General Public License as described below.
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 59 Temple
# Place, Suite 330, Boston, MA 02111-1307 USA
#
# Further information about the GNU GPL is available at:
# http://www.gnu.org/copyleft/gpl.ja.html

# Copyright (C) 2013 Oz Nahum  <nahumoz@gmail.com>

# The Original gpdfx was obtained from https://github.com/lehner/gpdfx.
# The changed done are mainly to replace the shell script with a Python
# method so that the whole GUI and Converter are contained in on file.

# These changed ease the installation and usage of this little useful tool
# a little bit

# added button selection to text.

import pygtk
pygtk.require('2.0')
import gtk
import poppler
import sys
import os
import subprocess as sp
import tempfile
import shutil


def ConverPartPDF(fname, fout, page, left, top, right, bottom):
    tdir = tempfile.mkdtemp()
    shutil.copy(fname, os.path.join(tdir, 'i.pdf'))

    lines = """
\\documentclass{{article}}
\\usepackage[left=0cm,right=0cm,bottom=0cm,top=0cm]{{geometry}}
\\usepackage{{graphicx}}
\\begin{{document}}
\\includegraphics[page={0},trim={1} {2} {3} {4},clip]{{{5}/i.pdf}}
\\end{{document}}
            """.format(page, left, bottom, right, top, tdir)

    with open(os.path.join(tdir, 'o.tex'), 'w') as output:
        output.write(lines)

    sp.call('pdflatex o.tex', shell=True, cwd=tdir)
    sp.call('pdfcrop o.pdf', shell=True, cwd=tdir)
    sp.call(['gs', '-q', '-sDEVICE=pdfwrite', '-dNOPAUSE',
            '-dBATCH', '-sOutputFile='+fout, '-f',
            os.path.join(tdir, 'o-crop.pdf')],
            cwd=tdir)

    shutil.rmtree(tdir)


class Poprender(object):

    def __init__(self):
        self.fn = os.path.expanduser(sys.argv[1])
        self.fn = os.path.expandvars(self.fn)
        self.fn = os.path.abspath(self.fn)
        uri = "file://" + self.fn

        try:
            self.document = poppler.document_new_from_file(uri, None)
        except:
            sys.exit(1)

        self.n_pages = self.document.get_n_pages()

        self.current_page = self.document.get_page(0)
        self.n_page = 1
        self.width, self.height = self.current_page.get_size()

        self.scale = 1
        self.sel = False

        self.win = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.win.set_default_size(600, 600)
        self.win.set_title(self.fn)
        self.win.connect("delete-event", gtk.main_quit)

        adjust = gtk.Adjustment(1, 1, self.n_pages, 1, 5)
        page_selector = gtk.SpinButton(adjust, 0, 0)
        page_selector.connect("value-changed", self.on_changed)

        lab = gtk.Label('Page')

        hbox = gtk.HBox(False, 0)

        vbox = gtk.VBox(False, 0)
        vbox.pack_start(hbox, False, False, 0)

        hbox.pack_start(lab, False, False, 4)
        hbox.pack_start(page_selector, False, False, 0)

        adjust = gtk.Adjustment(100, 25, 400, 25, 100)
        scale_selector = gtk.SpinButton(adjust, 0, 0)
        scale_selector.connect("value-changed", self.on_scale_changed)

        lab = gtk.Label('Zoom/%')

        hbox.pack_start(lab, False, False, 4)
        hbox.pack_start(scale_selector, False, False, 0)

        b_sel_topdf = gtk.Button('Selection to PDF')
        b_sel_topdf.connect("clicked", self.on_export)

        b_clear_sel = gtk.Button('Clear Selection')
        b_clear_sel.connect("clicked", self.on_clear_sel)

        b_sel_totext = gtk.Button('Selection to Text')
        b_sel_totext.connect("clicked", self.on_text)

        hbox.pack_start(b_clear_sel, False, False, 4)
        hbox.pack_start(b_sel_topdf, False, False, 0)
        hbox.pack_start(b_sel_totext, False, False, 0)

        self.sw = gtk.ScrolledWindow()
        self.sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.dwg = gtk.DrawingArea()
        self.dwg.set_size_request(int(self.width), int(self.height))
        self.dwg.connect("expose-event", self.on_expose)

        self.sw.connect("button-press-event", self.on_btn_pressed)
        self.sw.connect("button-release-event", self.on_btn_released)
        self.sw.connect("motion-notify-event", self.on_mouse_move)

        eventbox = gtk.EventBox()
        eventbox.add(self.dwg)

        self.sw.add_with_viewport(eventbox)
        self.dwg.modify_bg(gtk.STATE_NORMAL,
                           gtk.gdk.Color(50000, 50000, 50000))

        vbox.pack_start(self.sw, True, True, 0)

        self.win.add(vbox)
        self.win.show_all()

    def sel_pos_clip(self):
        if self.sel_x > self.width:
            self.sel_x = self.width
        if self.sel2_x > self.width:
            self.sel2_x = self.width
        if self.sel_y > self.height:
            self.sel_y = self.height
        if self.sel2_y > self.height:
            self.sel2_y = self.height

        if self.sel_x < 0:
            self.sel_x = 0
        if self.sel2_x < 0:
            self.sel2_x = 0
        if self.sel_y < 0:
            self.sel_y = 0
        if self.sel2_y < 0:
            self.sel2_y = 0

    def on_btn_pressed(self, widget, event):
        "excuted when mouse is pressed"

        if event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
            menu = gtk.Menu()
            menu_item = gtk.MenuItem("A")
            menu.append(menu_item)
            menu_item.show()
            menu.popup(None, None, None, event.button, event.time, None)

        if event.button == 1:

            self.sel_x = event.x/self.scale
            self.sel_y = event.y/self.scale
            self.sel2_x = event.x/self.scale
            self.sel2_y = event.y/self.scale
            self.sel_pos_clip()
            self.sel = True

    def on_btn_released(self, widget, event):
        self.sel2_x = event.x/self.scale
        self.sel2_y = event.y/self.scale
        self.sel_pos_clip()
        self.dwg.queue_draw()

    def on_mouse_move(self, widget, event):
        "called after the selection rectangle is shown"
        self.sel2_x = event.x/self.scale
        self.sel2_y = event.y/self.scale
        self.sel_pos_clip()
        self.dwg.queue_draw()

    def on_changed(self, widget):
        self.n_page = widget.get_value_as_int()
        self.current_page = self.document.get_page(widget.get_value_as_int()-1)
        self.width, self.height = self.current_page.get_size()
        self.dwg.set_size_request(int(self.width*self.scale),
                                  int(self.height*self.scale))
        self.dwg.queue_draw()

    def on_scale_changed(self, widget):
        self.scale = widget.get_value_as_int()/100.0
        self.dwg.set_size_request(int(self.width*self.scale),
                                  int(self.height*self.scale))
        self.dwg.queue_draw()

    def cr_draw(self, cr, width, height, scale):
        "draw pdf on the canvas"

        if scale != 1:
            cr.scale(scale, scale)
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        self.current_page.render(cr)

        if self.sel:
            cr.set_source_rgba(0, 0, 0.5, 0.9)
            cr.set_line_width(1)
            cr.rectangle(self.sel_x, self.sel_y, self.sel2_x-self.sel_x,
                         self.sel2_y-self.sel_y)
            cr.stroke_preserve()
            cr.set_source_rgba(0, 0, 1, 0.2)
            cr.fill()

    def on_expose(self, widget, event):
        cr = widget.window.cairo_create()
        self.cr_draw(cr, self.width, self.height, self.scale)

    def on_clear_sel(self, widget):
        self.sel = False
        self.dwg.queue_draw()

    def on_text(self, widget):
        if self.sel:
            rect = poppler.Rectangle()
            rect.x1, rect.x2 = self.sel, self.sel2_x
            rect.y1, rect.y2 = self.sel_y, self.sel2_y
            text = poppler.Page.get_selected_text(self.current_page,
                                                  poppler.SELECTION_GLYPH,
                                                  rect)

            self.clipboard = gtk.Clipboard(gtk.gdk.display_get_default(),
                                           "CLIPBOARD")
            self.clipboard.set_text(text)

    def on_export(self, widget):

        if self.sel:

            if self.sel_x > self.sel2_x:
                tmp = self.sel_x
                self.sel_x = self.sel2_x
                self.sel2_x = tmp

            if self.sel_y > self.sel2_y:
                tmp = self.sel_y
                self.sel_y = self.sel2_y
                self.sel2_y = tmp

            ch = gtk.FileChooserDialog("Filename for selection PDF", None,
                                       gtk.FILE_CHOOSER_ACTION_SAVE,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))
            ch.set_do_overwrite_confirmation(True)
            fnout = None
            if ch.run() == gtk.RESPONSE_OK:
                fnout = ch.get_filename()
            ch.destroy()

            if fnout is not None:

                ConverPartPDF(self.fn, fnout, self.n_page,
                              self.sel_x, self.sel_y,
                              self.width-self.sel2_x,
                              self.height-self.sel2_y)

    def main(self):
        gtk.main()


if __name__ == '__main__':
    try:
        if len(sys.argv) == 2:
            pop = Poprender()
            pop.main()
        else:
            print "Usage:"
            print os.path.basename(sys.argv[0]) + " filename.pdf"
    except KeyboardInterrupt:
        __name__
