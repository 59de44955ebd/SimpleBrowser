from webview2.winapp.const import *
from webview2.winapp.dlls import user32
from webview2.winapp.controls.tabcontrol import *


########################################
# Helper class to keep horizontal and vertical tabs in sync
########################################
class Tabs:

    ########################################
    #
    ########################################
    def __init__(self, tabcontrol, listbox):
        self.tabcontrol = tabcontrol
        self.listbox = listbox
        self._tab_id = 0

    ########################################
    #
    ########################################
    def new_tab_id(self):
        tab_id = self._tab_id
        self._tab_id += 1
        return tab_id

    ########################################
    #
    ########################################
    def get_tab_id_for_index(self, idx):
        return user32.SendMessageW(self.listbox.hwnd, LB_GETITEMDATA, idx, 0)

    ########################################
    #
    ########################################
    def get_index_for_tab_id(self, tab_id):
        cnt = user32.SendMessageW(self.listbox.hwnd, LB_GETCOUNT, 0, 0)
        for idx in range(cnt):
            if user32.SendMessageW(self.listbox.hwnd, LB_GETITEMDATA, idx, 0) == tab_id:
                return idx

    ########################################
    #
    ########################################
    def add_tab(self, tab_id, tab_name, idx_image, selected = False):
        idx = self.tabcontrol.get_item_count()

        tie = TCITEMW()
        tie.mask = TCIF_TEXT | TCIF_PARAM | TCIF_IMAGE
        tie.pszText = tab_name
        tie.iImage = idx_image
        tie.lParam = tab_id
        self.tabcontrol.insert_item(idx, tie)

        self.listbox.add_item(tab_name, tab_id, idx_image)

        if selected:
            self.tabcontrol.set_cur_sel(idx)
            user32.SendMessageW(self.listbox.hwnd, LB_SETCURSEL, idx, 0)

        return idx

    ########################################
    #
    ########################################
    def select_tab(self, idx):
        self.tabcontrol.set_cur_sel(idx)
        user32.SendMessageW(self.listbox.hwnd, LB_SETCURSEL, idx, 0)

    ########################################
    #
    ########################################
    def delete_tab(self, idx):
        self.tabcontrol.delete_item(idx)
        self.listbox.delete_item(idx)

    ########################################
    #
    ########################################
    def delete_all_tabs(self):
        self.tabcontrol.delete_all_items()
        self.listbox.delete_all_items()

    ########################################
    #
    ########################################
    def rename_tab(self, idx, tab_name):
        self.tabcontrol.set_item_text(idx, tab_name)

        tab_id = self.get_tab_id_for_index(idx)
        is_selected = idx == user32.SendMessageW(self.listbox.hwnd, LB_GETCURSEL, 0, 0)
        user32.SendMessageW(self.listbox.hwnd, LB_DELETESTRING, idx, 0)
        user32.SendMessageW(self.listbox.hwnd, LB_INSERTSTRING, idx, tab_name)
        user32.SendMessageW(self.listbox.hwnd, LB_SETITEMDATA, idx, tab_id)
        if is_selected:
            user32.SendMessageW(self.listbox.hwnd, LB_SETCURSEL, idx, 0)

    ########################################
    #
    ########################################
    def update_icon(self, idx, idx_image):
        tci = TCITEMW()
        tci.mask = TCIF_IMAGE
        tci.iImage = idx_image
        self.tabcontrol.set_item(idx, tci)
        self.listbox.update_icon(idx, idx_image)

    ########################################
    # tab_id, tab_name, idx_image
    ########################################
    def move_tab(self, idx_old, idx_new, vertical_only = False):
        tab_id = self.get_tab_id_for_index(idx_old)

        buf = create_unicode_buffer(MAX_TAB_TEXT_LEN)
        user32.SendMessageW(self.listbox.hwnd, LB_GETTEXT, idx_old, buf)
        tab_name = buf.value

        if not vertical_only:
            # a) TabControl
            tie = TCITEMW()
            tie.mask = TCIF_IMAGE
            user32.SendMessageW(self.tabcontrol.hwnd, TCM_GETITEMW, idx_old, byref(tie))
            user32.SendMessageW(self.tabcontrol.hwnd, TCM_DELETEITEM, idx_old, 0)
            tie.mask = TCIF_TEXT | TCIF_PARAM | TCIF_IMAGE
            tie.pszText = tab_name
            tie.cchTextMax = len(tab_name)
            tie.lParam = tab_id
            self.tabcontrol.insert_item(idx_new, tie)
            self.tabcontrol.set_cur_sel(idx_new)

        # b) ListBox
        user32.SendMessageW(self.listbox.hwnd, LB_DELETESTRING, idx_old, 0)
        user32.SendMessageW(self.listbox.hwnd, LB_INSERTSTRING, idx_new, tab_name)
        user32.SendMessageW(self.listbox.hwnd, LB_SETITEMDATA, idx_new, tab_id)
        user32.SendMessageW(self.listbox.hwnd, LB_SETCURSEL, idx_new, 0)
