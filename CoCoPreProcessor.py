import re
import sys
import os
from tkinter import Tk, filedialog, Listbox, Label, Scrollbar, Frame, Entry,Button
from lxml import html, etree
from lxml.html.clean import Cleaner
from functools import partial

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

def get_list(event):
    """
    function to read the listbox selection
    and put the result in an entry widget
    """
    vw = listboxWords.yview()
    # get selected line index
    index = listboxWords.curselection()[0]
    # get the line's text
    seltext = listboxWords.get(index)
    # delete previous text in enter1
    entryWords.delete(0, 100)
    # now display the selected text
    entryWords.insert(0, seltext)
    listboxWords.yview_moveto(vw[0])

def replace_list():
    """
    save the current listbox contents to a file
    """
    # get a list of listbox lines
    temp_list = list(listboxWords.get(0, 'end'))
    for idx in reversed(range(len(lAllFalseWordMatches))):
        if lAllFalseWordMatches[idx] == temp_list[idx]:
            lAllFalseWordMatches.pop(idx)
            temp_list.pop(idx)

    for e in leTextElements:
        # regex match on every text element to check whether it matches a wrongfully separated word
        # print(e.text)
        for repEl in range(len(temp_list)):
            if e.text:
                e.text = e.text.replace(lAllFalseWordMatches[repEl], temp_list[repEl])
    tk.destroy()
# File Dialog to choose htm-file
tk = Tk()
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
    # new = new.replace('\xa0', ' ')                                          # replaces non breaking spaces
    new = re.sub(r"(?sm)(?<=[a-zöüä\,;\xa0])\s*?</p>\s*?<p>(?=[a-zöäü])", ' ', new)  # removes wrong line breaks (BETA)
    fo.write(new)
    fo.close()

# open temp file for parsing
with open('tmp.htm', 'r+', encoding="utf-8") as input_file:
    tree = html.parse(input_file)

    # compile footnote patterns as regex object
    regFootnote = [
        re.compile('\s*\d{1,2}\s*'),
        re.compile('\s*\*{1,9}\s*'),
        re.compile('\s*\*{1,9}\)\s*'),
        re.compile('\s*[a-z]\s*'),
        re.compile('\s*\d{1,2}\)\s*'),
        re.compile('\s*\(\d{1,2}\)\s*')
    ]

    # compile number format as regex objects
    regNumbers = [
        re.compile('(^\s*?[-+$]{0,3}\s*?\(?\d{1,3}\)?[ €$%]{0,2}$)', re.MULTILINE),                        # 123 has to be first, to prevent double matches
        re.compile('(^\s*?[-+€]{0,3}\s*?\(?\d{1,3}(\.\d{3})*?(,\d{1,5})?\)?\s*?[€%]?\s*?$)', re.MULTILINE),  # 123.123,12000 ; 123,1 ; 123
        re.compile('(^\s*?[-+$]{0,3}\s*?\(?\d{1,3}(,\d{3})*?(\.\d{1,5})?\)?\s*?[$%]?\s*?$)', re.MULTILINE),  # 123,123.12 ; 123.1 ; 123
        re.compile('(^\s*?[-+€]{0,3}\s*?\(?\d{1,3}(\s\d{3})*?(,\d{1,5})?\)?\s*?[€%]?\s*?$)', re.MULTILINE),  # 123 123,12 ; 123,1 ; 123
        re.compile('(^\s*?[-+$]{0,3}\s*?\(?\d{1,3}(\s\d{3})*?(\.\d{1,5})?\)?\s*?[€%]?\s*?$)', re.MULTILINE), # 123 123.12 ; 123.1 ; 123
        # other allowed cell content
        re.compile('^[-.,\s]+$', re.MULTILINE),                                                  # empty cells and placeholder -,.
        re.compile('^\s*?(19|20)\d{2}\s*?$', re.MULTILINE),                                      # year 1900 - 2099
        re.compile('^\s*?[0123]?\d[./-][0123]?\d[./-](19|20)?\d{2}\s*?$', re.MULTILINE),               # dates 12.02.1991; 12.31.91: 12.31.2091
        re.compile('^.*[A-Za-z]{2,}.*$', re.DOTALL),                                              # text
        re.compile('^\s*?(in)?\s*?(T|Tsd|Mio|Mrd)?\.?\s?[€$]\s*?$', re.MULTILINE)  # T€, Mio. €, Mrd. €, in €
    ]

    regHeaderContent = [
        regNumbers[7],                                      # dates
        regNumbers[6],                                      # year
        regNumbers[9]                                       # T€, Mio. €, Mrd. €, in €
    ]

    regUnorderedList = [
        re.compile('^\s*?[►•■-]\s', re.MULTILINE)
    ]

    regFalseWords = [
        re.compile(r'(\b[A-ZÖÄÜa-zäöüß][a-zäöüß]*?[a-zäöüß][A-ZÄÖÜ][a-zäöüß]*?\b)', re.MULTILINE),          # CashFlow, cashFlow
        re.compile(r'(\b[A-ZÖÄÜa-zäöüß][a-zäöüß]*?\b-\b[a-zäöüß]{1,}?\b)', re.MULTILINE),                 # ex-terne, Ex-terne
        re.compile(r'\b[A-ZÖÄÜa-zäöüß]{1,}?soder\b', re.MULTILINE),                                   #  Unternehmungsoder
        re.compile(r'\b[A-ZÖÄÜa-zäöüß]{1,}?sund\b', re.MULTILINE)                                       # Unternehmungsund
    ]

    # replace </p><p> in tables with <br>
    # takes the longest, might find better alternative
    for td in tree.xpath('//td[count(p)>1]'):
        i = 0;
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

    # remove li tags in td elements
    for li in tree.xpath('//td/li'):
        li.drop_tag()

    # remove empty table rows
    for row in tree.xpath('//tr[* and not(*[node()])]'):
        row.getparent().remove(row)

    # remove unwanted tags
    cleaner = Cleaner(
        remove_tags=['a', 'head', 'div'],
        style=True,
        meta=True,
        remove_unknown_tags=False,
        page_structure=False
    )
    tree = cleaner.clean_html(tree)

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

    # check numbers in table cells
    # get all tables that are not footnote tables
    leStandardTables = tree.xpath('//table[not(@class="footnote")]')
    lFalseNumberMatches = []
    for table in leStandardTables:
        leSubtables = []
        iFormatCount = [0] * len(regNumbers)
        # select all non-empty td-elements, beginning at second column
        leSubtables.append(table.xpath('.//tr/td[position() > 1]'))
        for row in leSubtables:
            for cell in row:
                cell_format = [0] * len(regNumbers)
                for i in range(len(regNumbers)):
                    # breaks after first match
                    if cell.text is not None and regNumbers[i].fullmatch(str(cell.text)):
                        cell_format[i] += 1
                        break
                if sum(cell_format):
                    iFormatCount = [a + b for a, b in zip(iFormatCount, cell_format)]
                else:
                    lFalseNumberMatches.append(cell.text)

    # check false word separations
    # get all elements that contain text (p/h1/h2/h3)
    leTextElements = tree.xpath('.//*[normalize-space(text())]')
    # print(textElements)
    lAllFalseWordMatches = []
    for e in leTextElements:
        # regex match on every text element to check whether it matches a wrongfully separated word
        # print(e.text)
        if e.text:
            for regex_match in regFalseWords:
                lCurrentMatches = regex_match.findall(e.text)
                if len(lCurrentMatches):
                    lAllFalseWordMatches.extend(lCurrentMatches)
    # remove duplicates from match list
    lAllFalseWordMatches = list(dict.fromkeys(lAllFalseWordMatches))

    # set table headers row for row
    for table in leStandardTables:
        fHeader = False
        fBreakOut = False
        iHeaderRows = -1    # -1 for later comparison with 0 index
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

    # tkinter UI
    if len(lFalseNumberMatches) or len(lAllFalseWordMatches):
        # MASTER WINDOW
        tk.title('False formatted numbers and words')
        masterLabel = Label(tk, text='Double Click to copy')
        masterLabel.pack(side='top')

        # FRAME 1
        frameNumbers = Frame(tk, width=25, height=50)
        frameNumbers.pack(fill='y', side='left')
        # LISTBOX 1
        listboxNumbers = Listbox(frameNumbers, width=20, height=50)
        listboxNumbers.pack(side='left', expand=True)
        listboxNumbers.bind('<Double-Button-1>', listbox_copy)
        # SCROLLBAR 1
        scrollbarNumbers = Scrollbar(frameNumbers, orient="vertical")
        scrollbarNumbers.config(command=listboxNumbers.yview)
        scrollbarNumbers.pack(side="left", fill="y")
        # CONFIG 1
        listboxNumbers.config(yscrollcommand=scrollbarNumbers.set)
        print(lFalseNumberMatches)
        for e in range(len(lFalseNumberMatches)):
            listboxNumbers.insert(e, lFalseNumberMatches[e])

        # FRAME 2
        frameWords = Frame(tk, width=50, height=50)
        frameLbWords = Frame(frameWords, width=45, height=48)
        frameLbWords.pack(side='bottom')
        frameWords.pack(fill='y', side='left')
        # LISTBOX 2
        listboxWords = Listbox(frameLbWords, width=45, height=48)
        listboxWords.pack(side='left', expand=True)
        # falseWord_MSB.bind('<Double-Button-1>', listbox_copy)
        listboxWords.bind('<ButtonRelease-1>', get_list)
        # SCROLLBAR 2
        scrollbarWords = Scrollbar(frameLbWords, orient="vertical")
        scrollbarWords.config(command=listboxWords.yview)
        scrollbarWords.pack(side="left", fill="y")
        # CONFIG 2
        listboxWords.config(yscrollcommand=scrollbarWords.set)
        for e in range(len(lAllFalseWordMatches)):
            listboxWords.insert(e, lAllFalseWordMatches[e])

        # ENTRY BOX
        # use entry widget to display/edit selection
        entryWords = Entry(frameWords, width=50, bg='yellow')
        entryWords.insert(0, 'Click on an item in the listbox')
        entryWords.pack(side='top')
        entryWords.bind('<Return>', partial(set_list, listboxWords, entryWords))
        entryWords.focus_force()
        button1 = Button(frameWords, text='REPLACE AND QUIT', command=replace_list)
        button1.pack(side='top')

        tk.mainloop()

    # wrap all table contents in p-tags
    wrap(tree, "p")
    # write to new file in source folder
    tree.write(os.path.splitext(tk.filename)[0] + '_modified.htm', encoding='UTF-8', method='html')

os.remove('tmp.htm')  # remove original

