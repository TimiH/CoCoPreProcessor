import re
import sys
import os
from tkinter import Tk, filedialog, Listbox, Label, Scrollbar, Frame, Entry, Button, BooleanVar, StringVar, Checkbutton
from lxml import html, etree
from lxml.html.clean import Cleaner
from functools import partial

# global lists
lAllFalseWordMatches = []
lFalseNumberMatches = []

# global flags
bFoundError = False

##################
# REGEX PATTERNS #
##################

# compile footnote patterns as regex object
regFootnote = [
    re.compile('\s*\d{1,2}\s*'),
    re.compile('\s*\(?\*{1,9}\)?\s*'),
    re.compile('\s*[a-z]\s*'),
    re.compile('\s*\d{1,2}\)\s*'),
    re.compile('\s*[(\[]\d{1,2}[)\]]\s*')
]

# compile number format as regex objects
regNumbers = [
    re.compile('(^\s*?\(?\s*?[-+$]{0,3}\s*?\d{1,3}[ €$%]{0,2}\s*?\)?$)', re.MULTILINE),
    # 123 has to be first, to prevent double matches
    re.compile('(^\s*?\(?\s*?[-+€]{0,3}\s*?\d{1,3}(\.\d{3})*?(,\d{1,5})?\s*?[€%]?\s*?\)?\s*?$)', re.MULTILINE),
    # 123.123,12000 ; 123,1 ; 123
    re.compile('(^\s*?\(?\s*?[-+$]{0,3}\s*?\d{1,3}(,\d{3})*?(\.\d{1,5})?\s*?[$%]?\s*?\)?\s*?$)', re.MULTILINE),
    # 123,123.12 ; 123.1 ; 123
    re.compile('(^\s*?\(?\s*?[-+€]{0,3}\s*?\d{1,3}(\s\d{3})*?(,\d{1,5})?\s*?[€%]?\s*?\)?\s*?$)', re.MULTILINE),
    # 123 123,12 ; 123,1 ; 123
    re.compile('(^\s*?\(?\s*?[-+$]{0,3}\s*?\d{1,3}(\s\d{3})*?(\.\d{1,5})?\s*?[€%]?\s*?\)?\s*?$)', re.MULTILINE),
    # 123 123.12 ; 123.1 ; 123
    re.compile('^\s*?(%|n\/a|n\.a)\s*?$', re.IGNORECASE),

    # other allowed cell content
    re.compile('^[-.,§\s]+$', re.MULTILINE),  # empty cells and placeholder -,.
    re.compile('^\s*?(19|20)\d{2}\s*?$', re.MULTILINE),  # year 1900 - 2099
    re.compile('^\s*?\(?[0123]?\d?[./-]?[0123]?\d[./-](19|20)?\d{2}\)?\s*?$', re.MULTILINE),
    # dates 12.02.1991; 12.31.91: 12.31.2091
    re.compile('^.*[A-Za-z]{2,}.*$', re.DOTALL),  # text
    re.compile('^\s*?(in)?\s*?(TEUR|Tsd|Mio|Mrd|Jahre|T)?\.?\s?[€$]\s*?$', re.IGNORECASE | re.MULTILINE)
    # T€, Mio. €, Mrd. €, in €
]

regHeaderContent = [
    regNumbers[8],  # dates
    regNumbers[7],  # year
    regNumbers[10],  # T€, Mio. €, Mrd. €, in €
    re.compile('^\s*?(in)?\s*?(TEUR|TSD|MRD|EUR)?\s*?$', re.IGNORECASE | re.MULTILINE),  # T€, Mio. €, Mrd. €, in €
    re.compile('^\s*?[0123]?\d\.?\s*?(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s*?(19|20)?\d{2}\s*?$',
               re.IGNORECASE | re.MULTILINE),
    re.compile('^\s*?[0123]?\d\.?\s*?(Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dec)\.?\s*?(19|20)?\d{2}\s*?$',
               re.IGNORECASE | re.MULTILINE)
]

regUnorderedList = [
    re.compile('^\s*?[►•·■\-□^→]\s?', re.MULTILINE)
]

regFalseWords = [
    re.compile(r'(\b[A-ZÖÄÜa-zäöüß][a-zäöüß]*?[a-zäöüß][A-ZÄÖÜ][a-zäöüß]*?\b)', re.MULTILINE),  # CashFlow, cashFlow
    re.compile(r'(\b[A-ZÖÄÜa-zäöüß][a-zäöüß]*?\b-\b[a-zäöüß]{1,}?\b)', re.MULTILINE),  # ex-terne, Ex-terne
    re.compile(r'\b[A-ZÖÄÜa-zäöüß]{1,}?soder\b', re.MULTILINE),  # Unternehmungsoder
    re.compile(r'\b[A-ZÖÄÜa-zäöüß]{1,}?sund\b', re.MULTILINE)  # Unternehmungsund
]

# get list of allowed text elements
lAllowedWords = open('allowed_words.txt', encoding='UTF-8').read().splitlines()

# get list of sup-always elements
lSupElements = [
    '©',
    '®',
    '™'
]

#####################
# TKINTER FUNCTIONS #
#####################
tk = Tk()


def wrap(root, tag):
    # find <td> elements that do not have a <p> element
    cells = etree.XPath("//td[not(p)]")(root)
    for cell in cells:
        # Create new <p> element
        e = etree.Element(tag)
        # Set the <p> element text from the parent
        e.text = cell.text
        # Clear the parent text because it is now in the <p> element
        cell.text = None
        # Move the parents children and make them the <p> element's children
        # (because the span on line 10 of the input file should be nested)
        for child in cell.getchildren():
            # This actually moves the child from the <td> element to the <p> element
            e.append(child)
        # Set the new <p> element as the cell's child
        cell.append(e)


# UI for number checks
def listbox_copy(lb):
    tk.clipboard_clear()
    w = lb.widget
    selected = int(w.curselection()[0])
    tk.clipboard_append(w.get(selected))


def set_list(list, entry, event):
    """
    insert an edited line from the entry widget
    back into the listbox
    """
    vw = list.yview()
    index = list.curselection()[0]

    # delete old listbox line
    list.delete(index)

    # insert edited item back into listbox1 at index
    list.insert(index, entry.get())
    list.yview_moveto(vw[0])


def get_list(list, entry, event):
    """
    function to read the listbox selection
    and put the result in an entry widget
    """
    vw = list.yview()
    # get selected line index
    index = list.curselection()[0]
    # get the line's text
    seltext = list.get(index)
    # delete previous text in enter1
    entry.delete(0, 100)
    # now display the selected text
    entry.insert(0, seltext)
    list.yview_moveto(vw[0])


fReplaceWords = BooleanVar(value=1)
fReplaceNumbers = BooleanVar(value=1)


def replace_word_list(listbox):
    """
    replace the corrected listbox items with their counterparts
    """
    leTextElements = tree.xpath('.//*[normalize-space(text())]')
    # get a list of listbox lines
    temp_list = list(listbox.get(0, 'end'))
    tempAllFalseWords = lAllFalseWordMatches
    # print(len(lAllFalseWordMatches))
    for idx in reversed(range(len(tempAllFalseWords))):
        if tempAllFalseWords[idx] == temp_list[idx]:
            tempAllFalseWords.pop(idx)
            temp_list.pop(idx)

    for e in leTextElements:
        for repEl in range(len(temp_list)):
            if e.text:
                e.text = e.text.replace(tempAllFalseWords[repEl], temp_list[repEl])
    return lAllFalseWordMatches


def replace_number_list(listbox):
    leNumberElements = tree.xpath('//table[not(@class="footnote")]/tr/td[normalize-space(text())]')
    # get a list of listbox lines
    temp_list = list(listbox.get(0, 'end'))
    tempAllfalseNumbers = lFalseNumberMatches
    # print(lFalseNumberMatches)
    for idx in reversed(range(len(tempAllfalseNumbers))):
        if tempAllfalseNumbers[idx] == temp_list[idx]:
            tempAllfalseNumbers.pop(idx)
            temp_list.pop(idx)

    for e in leNumberElements:
        for repEl in range(len(temp_list)):
            if e.text:
                e.text = e.text.replace(tempAllfalseNumbers[repEl], temp_list[repEl])
    return lFalseNumberMatches


fFootnotetables = BooleanVar(value=1)


def set_footnote_tables():
    leAllTables = tree.xpath('//table')
    # check if tables are footnote tables
    for table in range(len(leAllTables)):
        leFirstColCells = []
        lbFootnoteMatches = []
        # print(len(tables[table].xpath('.//tr[1]/td')))
        # check first whether table is exactly 2 columns wide
        # print(table)
        if len(leAllTables[table].xpath('.//tr[last()]/td')) == 2:
            # create list from first column values
            leFirstColCells.append(leAllTables[table].xpath('.//tr/td[1]'))
            # flatten list
            leFirstColCells = [item for sublist in leFirstColCells for item in sublist]
            # check if any footnote regex pattern matches, if yes set corresponding matches list value to true
            for eCell in leFirstColCells:
                # remove sup, sub-tags if found
                for el in eCell:
                    if el.tag == 'sup' or el.tag == 'sub':
                        el.drop_tag()
                # create list with bool values of every regex, td-value match
                if eCell.text is not None:
                    lbFootnoteMatches.append(any(list(reg.fullmatch(eCell.text) for reg in regFootnote)))
                else:
                    lbFootnoteMatches.append(False)
            # check if all footnote cell values matched with regex pattern
            if all(lbFootnoteMatches):
                # if yes set table attribute to "footnote" and insert anchors
                for eCell in leFirstColCells:
                    etree.SubElement(eCell, 'a', id='a' + str(table + 1) + str(leFirstColCells.index(eCell)))
                leAllTables[table].set('class', 'footnote')
            # clear lists
            leFirstColCells.clear()
            lbFootnoteMatches.clear()


# returns list of elements of cells of all false number matches
fFixNumbers = BooleanVar(value=1)


def get_false_Numbers(lFalseNumberMatches):
    # check numbers in table cells
    # get all tables that are not footnote tables
    leStandardTables = tree.xpath('//table[not(@class="footnote")]')
    for table in leStandardTables:
        leSubtables = []
        iFormatCount = [0] * len(regNumbers)
        # select all non-empty td-elements, beginning at second column
        leSubtables.append(table.xpath('.//tr/td[position() > 1 and text()]'))
        for row in leSubtables:
            for cell in row:
                cell.text = cell.xpath('normalize-space(text())')
                if cell.text == '':
                    break
                cell_format = [0] * len(regNumbers)
                for i in range(len(regNumbers)):
                    # breaks after first match
                    if cell.text is not None and regNumbers[i].fullmatch(str(cell.text)):
                        cell_format[i] += 1
                        break
                if sum(cell_format):
                    iFormatCount = [a + b for a, b in zip(iFormatCount, cell_format)]
                elif cell.text is not None:
                    if fFixNumbers.get():
                        if cell.find('br') is not None and re.fullmatch('[0-9,. -]*', cell.text):
                            cell.find('br').drop_tag()
                            if any(list(reg.fullmatch(re.sub(r'\s+', '', cell.text)) for reg in regNumbers[0:4])):
                                cell.text = re.sub(r'\s+', '', cell.text)
                        else:
                            lFalseNumberMatches.append(cell.text)
                    else:
                        lFalseNumberMatches.append(cell.text)
    return lFalseNumberMatches


# fSplitRowSpan = BooleanVar(value=1)
# # split rowspan cells
# def split_rowspan():
#     leRowspanTables = tree.xpath('//table[.//td[@rowspan]]')
#     # print(leRowspanTables)
#     eEmptyTd = etree.Element('td')
#     for table in leRowspanTables:
#         for tr in table.xpath('./tr[.//td[@rowspan]]'):
#             print('Row: ' + str(table.index(tr)))
#             for td in tr.xpath('./td[@rowspan]'):
#                 # for iRow in range(int(td.get('rowspan'))):
#                     # table.
#                 print(td)
#                 # td.attrib.pop('rowspan')
#                 table[table.index(tr)+1].insert(tr.index(td), eEmptyTd)
#                 # print('Cell: ' + str(tr.index(td)))
#
#         # for tr in table.xpath('./tr[//td[@rowspan]]'):

# returns list of strings of all false separated words
def get_false_Words(lAllFalseWordMatches):
    # check false word separations
    # get all elements that contain text (p/h1/h2/h3/td)
    leTextElements = tree.xpath('.//*[normalize-space(text())]')
    # print(textElements)
    for e in leTextElements:
        # regex match on every text element to check whether it matches a wrongfully separated word
        # print(e.text)
        if e.text:
            for regex_match in regFalseWords:
                lCurrentMatches = regex_match.findall(e.text)
                if len(lCurrentMatches):
                    lCurrentMatches = [elem for elem in lCurrentMatches if elem not in lAllowedWords]
                    lAllFalseWordMatches.extend(lCurrentMatches)
    return list(dict.fromkeys(lAllFalseWordMatches))


# sets header according to regex matches and empty first column cells
fSetHeaders = BooleanVar(value=1)
def set_headers():
    # set table headers row for row
    leStandardTables = tree.xpath('//table[not(@class="footnote")]')
    for table in leStandardTables:
        fHeader = False
        fBreakOut = False
        iHeaderRows = -1  # -1 for later comparison with 0 index
        for row in table:
            for cell in row:
                if cell.text is not None:
                    # first compare cell content to header content matches
                    # if anything matches, set current row to header row
                    if any(list(reg.fullmatch(cell.text) for reg in regHeaderContent)):
                        fHeader = True
                        iHeaderRows = table.index(row)
                    # then compare to number matches
                    # if it matches here the function quits and reverts back to previous header row
                    if any(list(reg.fullmatch(cell.text) for reg in regNumbers[0:4])):
                        # print('found number')
                        iHeaderRows = iOldHeaderRow
                        fBreakOut = True
                        break
            if fBreakOut:
                break
            iOldHeaderRow = iHeaderRows

            # get the first occuring row in which the first cell is not empty
        eFirstTextRow = table.xpath('./tr[td[position() = 1 and text()]][1]')
        if len(eFirstTextRow):
            # index of the first cell with text - 1 to get only empty cells
            iFirstTextCellRow = table.index(eFirstTextRow[0]) - 1
            if iHeaderRows <= iFirstTextCellRow:
                iHeaderRows = iFirstTextCellRow
                fHeader = True

        if fHeader:
            # create lists with header and body elements
            # this is needed at the beginning, because the position changes when adding header and body tags
            headers = table.xpath('.//tr[position() <= %s]' % str(iHeaderRows + 1))
            body = table.xpath('.//tr[position() > %s]' % str(iHeaderRows + 1))
            # create thead-/tbody-tags
            table.insert(0, etree.Element('tbody'))
            table.insert(0, etree.Element('thead'))

            # move rows to inside header or body
            for thead in headers:
                table.find('thead').append(thead)
            for tbody in body:
                table.find('tbody').append(tbody)


# set all unordered list elements according to regex matches, only for > 1 matches
fSetUnorderedList = BooleanVar(value=1)
def set_unordered_list():
    # find and set unordered lists
    leDashCandidates = []
    iDashCount = 0
    for p in tree.xpath('//body/p'):
        # check if beginning of paragraph matches safe list denominators
        if p.text:
            # if not check if "- " matches
            if regUnorderedList[0].match(p.text):
                iDashCount += 1
                # append to list for later tag change
                leDashCandidates.append(p)
            else:
                # if only one dash is present, remove last element from dash list (single list item could be confused with
                # wrong break)
                if iDashCount == 1:
                    leDashCandidates.pop()
                iDashCount = 0
    # iterate through dash list and change to unordered list
    for p in leDashCandidates:
        p.text = regUnorderedList[0].sub('', p.text)
        p.tag = 'li'


# remove empty rows
fRemoveEmptyRows = BooleanVar(value=1)
def remove_empty_rows():
    # remove empty table rows
    for row in tree.xpath('//tr[* and not(*[node()])]'):
        row.getparent().remove(row)


# merge marked tables vertically
fMergeTablesVertically = BooleanVar(value=1)
def merge_tables_vertically():
    global bFoundError
    leMergeTables = tree.xpath(
        '//table[tr[1]/td[1][starts-with(normalize-space(text()),"§§")] or tr[last()]/td[last()][starts-with(normalize-space(text()),"§§")]]')
    leToMerge = []
    fContinuedMerge = False
    for table in leMergeTables:
        iCols = []
        fStartMarker = table.xpath('./tr[1]/td[1][starts-with(normalize-space(text()),"§§")]')
        fEndMarker = table.xpath('./tr[last()]/td[last()][starts-with(normalize-space(text()),"§§")]')
        # check if table has end marker (§§)
        if fEndMarker:
            # and start marker?
            if fStartMarker:
                # is merge list empty?
                if not leToMerge:
                    # BUG
                    print('Error in marker start or end position! Check the markers in ABBYY!\n'
                          'Error found in table with start marker: ' + str(table.xpath('./tr[1]/td[1]/text()')) + '\n'
                                                                                                                  'and end marker: ' + str(
                        table.xpath('./tr[last()]/td[last()]/text()')))
                    fContinuedMerge = False
                    bFoundError = True
                    continue
                else:
                    leToMerge.append(table)
                    fContinuedMerge = True
            else:
                leToMerge.append(table)
                fContinuedMerge = True
        elif fStartMarker:
            if not leToMerge:
                # BUG
                print('Error in start marker position! Check the markers in ABBYY!\n'
                      'Error found in table with start marker: ' + str(table.xpath('./tr[1]/td[1]/text()')))
                fContinuedMerge = False
                bFoundError = True
                continue
            else:
                leToMerge.append(table)
                fContinuedMerge = False
        else:
            print('No markers detected, this shouldnt happen, report this bug!')
            bFoundError = True
            break
        # next table included in merge?
        # if not merge collected tables
        if not fContinuedMerge:
            # check if all tables in merge list have the same number of columns
            iColNumbers = []
            for mTable in leToMerge:
                lColTemp = []
                # get max number of columns in a row
                for row in mTable:
                    lColTemp.append(row.xpath('./td'))
                iColNumbers.append(max(len(x) for x in lColTemp))
            # do all merging candidates have the same number of columns?
            if len(set(iColNumbers)) == 1:
                # remove end marker
                # for first table
                leToMerge[0].xpath('./tr[last()]/td[last()]')[0].text = leToMerge[0].xpath('./tr[last()]/td[last()]')[
                    0].text.replace('§§', '')
                for i in range(1, len(leToMerge)):
                    # remove start markers
                    if leToMerge[i].xpath('./tr[1]/td[1]')[0].text is not None:
                        leToMerge[i].xpath('./tr[1]/td[1]')[0].text = leToMerge[i].xpath('./tr[1]/td[1]')[
                            0].text.replace('§§', '')
                    # remove end markers
                    # and every other table
                    if leToMerge[i].xpath('./tr[last()]/td[last()]')[0].text is not None:
                        leToMerge[i].xpath('./tr[last()]/td[last()]')[0].text = \
                        leToMerge[i].xpath('./tr[last()]/td[last()]')[0].text.replace('§§', '')
                    # append all rows from all tables to first table
                    for row in leToMerge[i]:
                        leToMerge[0].append(row)
                    # remove now empty table
                    leToMerge[i].getparent().remove(leToMerge[i])
            else:
                print(
                    'You try to merge tables with different amount of table columns. Fix this in ABBYY or CoCo! Tables will not be merged!')
                print('Table end marker: ' + str(leToMerge[0].xpath('./tr[last()]/td[last()]/text()')))
                print(iColNumbers)
                bFoundError = True
            leToMerge = []



fSupElements = BooleanVar(value=0)
def sup_elements(path, entry):
    with open(path, 'r', encoding='UTF-8') as fi, open('temp.htm', 'w', encoding='UTF-8') as fo:
        rawText = fi.read()
        fi.close()
        os.remove(path)
        lUserSupElements = entry.get().replace(' ', '').split(',')
        for sup in lUserSupElements:
            rawText = rawText.replace(sup, '<sup>' + sup + '</sup>')
        fo.write(rawText)
        fo.close()
        os.rename('temp.htm', path)
    # leTextNotHeader = tree.xpath('.//*[normalize-space(text()) and not(self::h1] and not(self::h2) and not(self::h3)')


fSpanHeaders = BooleanVar(value=0)


def set_span_headers(lSpanHeaders):
    for span in lSpanHeaders:
        span[0].drop_tag()
        span.tag = 'h3'


fRenamePictures = BooleanVar(value=1)
def rename_pictures():
    picFolder = os.path.splitext(tk.filename)[0] + '_files'
    if os.path.exists(picFolder):
        for filename in os.listdir(picFolder):
            base_file, ext = os.path.splitext(filename)
            if ext == ".png":
                # rename reference in htm file
                # get 'img' tag
                ePngPic = tree.xpath('//img[@src="' + os.path.basename(picFolder) + '/' + filename + '"]')
                # rename attribute "src"
                ePngPic[0].attrib['src'] = os.path.basename(picFolder) + '/' + base_file + '.jpg'
                # rename picture file
                os.rename(picFolder + '/' + filename, picFolder + '/' + base_file + ".jpg")


# generate htm file
def generate_file(entryCkb):
    if fRemoveEmptyRows.get():
        remove_empty_rows()
    if fMergeTablesVertically.get():
        merge_tables_vertically()
    if fSetUnorderedList.get():
        set_unordered_list()
    if fFootnotetables.get():
        set_footnote_tables()
    if fReplaceNumbers.get():
        replace_number_list(listboxNumbers)
    if fReplaceWords.get():
        replace_word_list(listboxWords)

    # if fSplitRowSpan.get():
    #     split_rowspan()
    if fSpanHeaders.get():
        set_span_headers(leSpanHeaders)
    if fSetHeaders.get():
        set_headers()
    if fRenamePictures.get():
        rename_pictures()
    # wrap all table contents in p-tags
    # wrap(tree, "p")
    # write to new file in source folder
    tree.write(os.path.splitext(tk.filename)[0] + '_modified.htm', encoding='UTF-8', method='html')
    if fSupElements.get():
        sup_elements(os.path.splitext(tk.filename)[0] + '_modified.htm', entryCkb)
    tk.destroy()

    #####################
    #     OPEN FILE     #
    #####################


if len(sys.argv) < 2:
    tk.filename = filedialog.askopenfilename(initialdir=r"C:\Users\blank\Desktop\XML", title="Select file",
                                             filetypes=(("HTML files", "*.htm"), ("all files", "*.*")))
else:
    tk.filename = sys.argv[1]

# open the file as string, to replace tag-based substrings
# much easier to do before parsing html
with open(tk.filename, 'r', encoding='UTF-8') as fi, \
        open('tmp.htm', 'w', encoding='UTF-8') as fo:
    new_str = fi.read()
    new = new_str.replace('CO2', 'CO<sub>2</sub>')  # replaces every occurrence of CO2
    new = new.replace('\u2013', '-')  # replaces en dash with normal dash
    new = new.replace('\xa0', ' ')  # replaces non breaking spaces
    # REMOVE WRONG LINE BREAK HERE BECAUSE I CANT FIGURE OUT HOW TO DO IT WITHIN THE PARSER
    new = re.sub(r"(?sm)(?<=[a-zöüä\,;\xa0])\s*?</p>\s*?<p>(?=[a-zöäü][^)])", ' ', new)
    fo.write(new)
    fo.close()

    ################
    # PARSING FILE #
    ################

with open('tmp.htm', 'r+', encoding="utf-8") as input_file:
    tree = html.parse(input_file)
    #################
    #  PREPARATIONS #
    #################

    # replace </p><p> in tables with <br>
    # takes the longest, might find better alternative
    for td in tree.xpath('//td[count(p)>1]'):
        i = 0
        x = len(td)
        for p in range(x):
            i += 1
            if i > x - 1:
                break
            td.insert(p + i, etree.Element('br'))

    # change all header hierarchies higher than 3 to 3
    for e in tree.xpath('//*[self::h4 or self::h5 or self::h6]'):
        e.tag = 'h3'

    # remove sup/sub tags from headlines
    for e in tree.xpath('//*[self::h1 or self::h2 or self::h3]/*[self::sup or self::sub]'):
        e.drop_tag()

    # remove p tags in tables
    for p in tree.xpath('//table//p'):
        # print(p.text)
        p.drop_tag()

    # strip all unnecessary white space
    for td in tree.xpath('//table//td'):
        if td.text is not None:
            td.text = td.text.strip()

    # remove li tags in td elements
    for li in tree.xpath('//td/li'):
        li.drop_tag()

    for tag in tree.xpath('//*[@class]'):
        # For each element with a class attribute, remove that class attribute
        tag.attrib.pop('class')

    # remove sup/sub tags in unordered list candidates and for non footnote candidates
    for sup in tree.xpath('//*[self:: sup or self::sub]'):
        if sup.text is None:
            sup.drop_tag()
        elif any(list(reg.fullmatch(sup.text) for reg in regUnorderedList)):
            sup.drop_tag()
        elif not any(list(reg.fullmatch(sup.text) for reg in regFootnote)):
            sup.drop_tag()

    # execute only if a formatted html file is used (ABBYY export formatted file)
    leSpanHeaders = []
    if tree.xpath('/html/head/style'):
        print('Found formatted File')
        # select all span tags that are the only thing present in a p tag (heading candidates)
        for span in tree.xpath('//*[self::span]/ancestor::p'):
            # check if tag contains more than just the span tag
            # if so skip it
            if span.text is None:
                # check if tag contains more than one span tag
                # if so skip it
                if len(span) == 1:
                    leSpanHeaders.append(span)

        for br in tree.xpath('//br[@*]'):
            br.drop_tag()

    # remove unwanted tags
    cleaner = Cleaner(
        remove_tags=['a', 'head', 'div', 'span'],
        style=True,
        meta=True,
        remove_unknown_tags=False,
        page_structure=False,
        inline_style=True
    )
    tree = cleaner.clean_html(tree)

    ############
    # BUILD UI #
    ############

    # MASTER WINDOW
    tk.title('CoCo PreProcessor UI')
    frameTop = Frame(tk, height=3)
    frameTop.pack(side='top', fill='x')
    masterLabel = Label(frameTop,
                        text='Double Click on list entry to copy to clipboard\nSingle Click to fix in yellow entry box. ENTER to confirm changes!',
                        width=55, font=('Arial', 10, 'bold'))
    masterLabel.pack(side='left')

    # FRAME 1
    frameNumbers = Frame(tk, width=25, height=50)
    frameLbNumbers = Frame(frameNumbers, width=45, height=48)
    frameLbNumbers.pack(side='bottom')
    frameNumbers.pack(fill='y', side='left')
    # LISTBOX 1
    listboxNumbers = Listbox(frameLbNumbers, width=20, height=48)
    listboxNumbers.pack(side='left', expand=True)
    listboxNumbers.bind('<Double-Button-1>', listbox_copy)

    # SCROLLBAR 1
    scrollbarNumbers = Scrollbar(frameLbNumbers, orient="vertical")
    scrollbarNumbers.config(command=listboxNumbers.yview)
    scrollbarNumbers.pack(side="left", fill="y")
    # CONFIG 1
    listboxNumbers.config(yscrollcommand=scrollbarNumbers.set)
    get_false_Numbers(lFalseNumberMatches)
    for e in range(len(lFalseNumberMatches)):
        listboxNumbers.insert(e, lFalseNumberMatches[e])
    # ENTRY BOX NUMBERS
    # use entry widget to display/edit selection
    entryNumbers = Entry(frameNumbers, width=25, bg='yellow')

    entryNumbers.pack(side='top')
    entryNumbers.bind('<Return>', partial(set_list, listboxNumbers, entryNumbers))
    listboxNumbers.bind('<ButtonRelease-1>', partial(get_list, listboxNumbers, entryNumbers))
    entryNumbers.focus_force()

    # FRAME 2
    frameWords = Frame(tk, width=50, height=50)
    frameLbWords = Frame(frameWords, width=45, height=48)
    frameLbWords.pack(side='bottom')
    frameWords.pack(fill='y', side='left')
    # LISTBOX 2
    listboxWords = Listbox(frameLbWords, width=45, height=48)
    listboxWords.pack(side='left', expand=True)
    listboxWords.bind('<Double-Button-1>', listbox_copy)
    # SCROLLBAR 2
    scrollbarWords = Scrollbar(frameLbWords, orient="vertical")
    scrollbarWords.config(command=listboxWords.yview)
    scrollbarWords.pack(side="left", fill="y")
    # CONFIG 2
    listboxWords.config(yscrollcommand=scrollbarWords.set)
    lAllFalseWordMatches = get_false_Words(lAllFalseWordMatches)
    for e in range(len(lAllFalseWordMatches)):
        listboxWords.insert(e, lAllFalseWordMatches[e])

    # ENTRY BOX WORDS
    # use entry widget to display/edit selection
    entryWords = Entry(frameWords, width=50, bg='yellow')
    entryWords.insert(0, 'Click on an item in the listbox')
    entryWords.pack(side='top')
    entryWords.bind('<Return>', partial(set_list, listboxWords, entryWords))
    listboxWords.bind('<ButtonRelease-1>', partial(get_list, listboxWords, entryWords))
    entryWords.focus_force()
    # buttonWords = Button(frameWords, text='REPLACE AND QUIT', command=replace_list)
    # buttonWords.pack(side='top')

    # FRAME 3
    frameChecks = Frame(tk, width=25, height=50)
    frameChecks.pack(fill='y', side='left')
    ckbHeaders = Checkbutton(frameChecks, anchor='w', text='convert headers', variable=fSetHeaders)
    ckbFootnotes = Checkbutton(frameChecks, anchor='w', text='convert footnotes', variable=fFootnotetables)
    ckbEmptyRows = Checkbutton(frameChecks, anchor='w', text='remove empty rows', variable=fRemoveEmptyRows)
    ckbWords = Checkbutton(frameChecks, anchor='w', text='replace fixed words', variable=fReplaceWords)
    ckbNumbers = Checkbutton(frameChecks, anchor='w', text='replace fixed numbers', variable=fReplaceNumbers)
    ckbVertMerge = Checkbutton(frameChecks, anchor='w', text='vertically merge tables (§§)',
                               variable=fMergeTablesVertically)
    ckbSpanHeaders = Checkbutton(frameChecks, anchor='w', text='analyze heading (BETA)', variable=fSpanHeaders)
    ckbRenamePics = Checkbutton(frameChecks, anchor='w', text='rename .png to .jpg', variable=fRenamePictures)

    ckbHeaders.pack(side='top', anchor='w')
    ckbFootnotes.pack(side='top', anchor='w')
    ckbEmptyRows.pack(side='top', anchor='w')
    ckbWords.pack(side='top', anchor='w')
    ckbNumbers.pack(side='top', anchor='w')
    ckbVertMerge.pack(side='top', anchor='w')
    ckbSpanHeaders.pack(side='top', anchor='w')
    ckbRenamePics.pack(side='top', anchor='w')

    # Sup check button
    labelCkb = Label(frameChecks, text='\nSuperscript elements')
    labelCkb.pack(side='top', anchor='w')
    frameCkb = Frame(frameChecks, width=25, height=5)
    frameCkb.pack(side='top')
    ckbSup = Checkbutton(frameCkb, anchor='w', variable=fSupElements)
    ckbSup.pack(side='left', anchor='w')
    entryCkb = Entry(frameCkb, width=23, )
    entryCkb.insert(0, ', '.join(lSupElements))
    entryCkb.pack(side='left')

    buttonGenerate = Button(frameChecks, height=3, width=20, bd=2, fg='white', font=('Arial', 15),
                            text='GENERATE FILE \n AND QUIT', command=partial(generate_file, entryCkb), bg='dark green')
    buttonGenerate.pack(side='bottom')
    tk.mainloop()

os.remove('tmp.htm')  # remove original
if bFoundError:
    input('Fix displayed errors and press ENTER to quit!')
