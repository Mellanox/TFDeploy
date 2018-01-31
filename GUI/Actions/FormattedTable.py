#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from Actions.Log import UniBorder

#############################################################################

class FormattedTable(object):

    BAR = []

    class Column(object):
    
        def __init__(self, name, adjust_width=True, min_width=1):
            self.name = name
            self.adjust_width = adjust_width
            self.width = min_width
    
    # -------------------------------------------------------------------- #
    
    class Group(object):
        
        def __init__(self, name):
            self.name = name
            self.width = 0
            self.columns = []
            
        # ---------------------------- #
        
        def calculate_width(self, is_csv):
            columns_width = 0
            for column in self.columns:
                columns_width += column.width
                
            num_cols = len(self.columns)
            if is_csv:
                columns_width += (num_cols - 1) * 2
            else:
                columns_width += (num_cols - 1) * 3

            group_name_width = (0 if self.name == None else len(self.name)) + num_cols
            if group_name_width > columns_width:
                delta = group_name_width - columns_width
                self.columns[num_cols - 1].width += delta
                self.width = group_name_width
            else:
                self.width = columns_width
    
    # -------------------------------------------------------------------- #
    
    def __init__(self):
        self.columns = []
        self.rows = []
        self.groups = []
        self.output = None
        self._bind = False
        
        ##########
        # Style: #
        ##########
        self.border_style = UniBorder.BORDER_STYLE_STRONG
        
    # -------------------------------------------------------------------- #
    
    def bind(self, output = sys.stdout, print_header = True):
        self.output = output
        self._bind = True
        if print_header:
            self._calculate_column_widths()
            self._calculate_group_widths(False)            
            self._print_headers()
            
    # -------------------------------------------------------------------- #
    
    def unbind(self):
        self._print_footers()
        self._bind = False
        
    # -------------------------------------------------------------------- #
    
    def add_column(self, column, group_name = None):
        num_groups = len(self.groups)
        
        if (num_groups == 0) or (group_name != self.groups[num_groups - 1].name):
            group = FormattedTable.Group(group_name)
            self.groups.append(group)
        else:
            group = self.groups[num_groups - 1]
        
        group.columns.append(column)
        self.columns.append(column)
        
    # -------------------------------------------------------------------- #
    
    def add_row(self, row):
        self.rows.append(row)
        if self._bind:
            self._print_row(row)
    
    # -------------------------------------------------------------------- #

    def add_bar(self):
        self.rows.append(FormattedTable.BAR)
    
    # -------------------------------------------------------------------- #
    
    def _has_groups(self):
        return (len(self.groups) > 1) or (self.groups[0].name != None) 
    
    # -------------------------------------------------------------------- #
    
    def _calculate_column_widths(self):
        for col_num in xrange(len(self.columns)):
            self.columns[col_num].width = self._calc_column_width(col_num)
            
    # -------------------------------------------------------------------- #
    
    def _calculate_group_widths(self, is_csv):
        if not self._has_groups():
            return

        for group in self.groups:
            group.calculate_width(is_csv)
        
    # -------------------------------------------------------------------- #
    
    def _print(self, text):
        self.output.write(text)

    
    # -------------------------------------------------------------------- #
        
    def NO_CONNECTIONS(self):
        return [False] * len(self.columns)

    # -------------------------------------------------------------------- #
    
    def COLUMN_CONNECTIONS(self):
        return [True] * len(self.columns)
    
    # -------------------------------------------------------------------- #
    
    def GROUP_CONNECTIONS(self):
        result = []
        for group in self.groups:
            result.extend([True] + [False] * (len(group.columns) - 1))
        return result
        
    # -------------------------------------------------------------------- #
    
    def _get_cell_value(self, row, col_num):
        return row[col_num] if col_num < len(row) else ""
    
    # -------------------------------------------------------------------- #
    
    def _get_vertical_position(self, has_top, has_bottom):
        return has_top * UniBorder.VERTICAL_POSITION_HAS_TOP + has_bottom * UniBorder.VERTICAL_POSITION_HAS_BOTTOM

    # -------------------------------------------------------------------- #
    
    def _get_horizonal_position(self, has_left, has_right):
        return has_left * UniBorder.HORIZONAL_POSITION_HAS_LEFT + has_right * UniBorder.HORIZONAL_POSITION_HAS_RIGHT
                                             
    # -------------------------------------------------------------------- #
    
    def _get_border_char_by_part(self, border_part):
        return UniBorder._border_chars[border_part][self.border_style]
    
    # -------------------------------------------------------------------- #
    
    def _get_border_part_by_direction(self, vertical_position, horizonal_position):
        return UniBorder._junction_part_by_position[vertical_position][horizonal_position]
    
    # -------------------------------------------------------------------- #
    
    def _get_border_char(self, has_top, has_bottom, has_left, has_right):
        vertical_position   = self._get_vertical_position(has_top, has_bottom)
        horizonal_position  = self._get_horizonal_position(has_left, has_right)
        border_part         = self._get_border_part_by_direction(vertical_position, horizonal_position)
        return self._get_border_char_by_part(border_part)
    
    # -------------------------------------------------------------------- #
    
    def _calc_column_width(self, col_num):
        column = self.columns[col_num]
        if not column.adjust_width:
            return column.width
        
        max_value_len = len(column.name)
        for row in self.rows:
            cell_value = self._get_cell_value(row, col_num)
            value_len = len(str(cell_value).decode("utf-8")) 
            if value_len > max_value_len:
                max_value_len = value_len
        
        return max(column.width, max_value_len)
            
    # -------------------------------------------------------------------- #
    
    def _print_bar(self, top_connnections, bottom_connections):
        
        bar_char = self._get_border_char_by_part(UniBorder.BORDER_PART_HORIZONAL_LINE)
        
        result = ""
        for col_num in xrange(len(self.columns)):
            result += self._get_border_char(top_connnections[col_num], bottom_connections[col_num], col_num != 0, True)
            result += bar_char * (self.columns[col_num].width + 2)
            
        result += self._get_border_char(top_connnections[0], bottom_connections[0], True, False)
        result += "\n"
        self._print(result)
    
    # -------------------------------------------------------------------- #
    
    def _print_headers(self):
        
        seperator = self._get_border_char_by_part(UniBorder.BORDER_PART_VERTICAL_LINE)

        ###########
        # Groups: #
        ###########
        if self._has_groups():
            self._print_bar(self.NO_CONNECTIONS(), self.GROUP_CONNECTIONS())
            result = seperator
            for group in self.groups:
                group_title = "" if group.name is None else group.name
                result += " %-*s " % (group.width, group_title)
                result += seperator
            result += "\n"
            self._print(result)
            self._print_bar(self.GROUP_CONNECTIONS(), self.COLUMN_CONNECTIONS())
        else:
            self._print_bar(self.NO_CONNECTIONS(), self.COLUMN_CONNECTIONS())
                    
        ############
        # Columns: #
        ############
        result = seperator
        for column in self.columns:
            result += " %-*s " % (column.width, column.name)
            result += seperator
        result += "\n"            
        self._print(result)
        self._print_bar(self.COLUMN_CONNECTIONS(), self.COLUMN_CONNECTIONS())
        
    # -------------------------------------------------------------------- #
    
    def _print_row(self, row):
        if row is FormattedTable.BAR:
            self._print_bar(self.COLUMN_CONNECTIONS(), self.COLUMN_CONNECTIONS())
            return
            
        seperator = self._get_border_char_by_part(UniBorder.BORDER_PART_VERTICAL_LINE)
        result = seperator
        for col_num in xrange(len(self.columns)):
            cell_width = self.columns[col_num].width
            cell_value = self._get_cell_value(row, col_num)
            result += " %-*s " % (cell_width, cell_value)
            result += seperator
        result += "\n"
        self._print(result)

    # -------------------------------------------------------------------- #

    def _print_footers(self):
        self._print_bar(self.COLUMN_CONNECTIONS(), self.NO_CONNECTIONS())        
    
    # -------------------------------------------------------------------- #
    
    def _print_csv_headers(self):
        
        ###########
        # Groups: #
        ###########
        if self._has_groups():        
            result = ""
            for group in self.groups:
                num_columns = len(group.columns)
                group_title = ("" if group.name is None else group.name) + "," * (num_columns - 1)
                result += "%-*s, " % (group.width, group_title)
            result += "\n"
            self._print(result)

        ############
        # Columns: #
        ############
        result = "" 
        for column in self.columns:
            result += "%-*s, " % (column.width, column.name)
        result += "\n"
        self._print(result)
        
    # -------------------------------------------------------------------- #
    
    def _print_csv_row(self, row):
        result = "" 
        for col_num in xrange(len(self.columns)):
            cell_width = self.columns[col_num].width
            cell_value = self._get_cell_value(row, col_num)
            result += "%-*s, " % (cell_width, cell_value)
        result += "\n"
        self._print(result)
        
    # -------------------------------------------------------------------- #
    
    def print_formatted(self, output_file = sys.stdout):
        
        self._calculate_column_widths()
        self._calculate_group_widths(False)
        
        self.output = output_file
        self._print_headers()
        for row in self.rows:
            self._print_row(row)
        self._print_footers()
            
    # -------------------------------------------------------------------- #
        
    def print_as_csv(self, output_file = sys.stdout):
        
        self._calculate_column_widths()
        self._calculate_group_widths(True)
        
        self.output = output_file
        self._print_csv_headers()
        for row in self.rows:
            self._print_csv_row(row)
        

###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

if __name__ == '__main__':
    table = FormattedTable()
    table.add_column(FormattedTable.Column("Column A"))
    table.add_column(FormattedTable.Column("Column B"))
    table.add_column(FormattedTable.Column("Column C"))
    table.add_column(FormattedTable.Column("Column D"))
    table.bind()
    table.add_row(["A1", "B1", "C1", "D1"])
    table.add_row(["A2", "B2", "C2", "D2"])
    table.add_bar()
    table.add_row(["A3", "B3", "C3", "D3"])
    table.unbind()
    table.print_as_csv()
