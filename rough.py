from bs4 import BeautifulSoup
import robot
import xml.etree.ElementTree as ET
from robot.libraries import XML
import sys, csv, io, glob, os, requests, re, argparse, datetime, time
from lxml import etree
import ftplib
from requests.exceptions import ConnectionError


tree = XML.XML()
 
def clear_content(tc):
    """Clears the content within a test case"""
    to_remove = ['kw', 'doc', 'metadata', 'tags']
    for tr in to_remove:
        remove_elem = tree.get_elements(tc, tr)
        for re in remove_elem:
            tc.remove(re)

def clear_suite(suite):
    """Clears the content of a suite"""
    to_remove = ['kw', 'doc', 'metadata', 'tags']
    for tr in to_remove:
        remove_elem = tree.get_elements(suite, tr)
        for re in remove_elem:
            suite.remove(re)
    for test in tree.get_elements(suite, 'test'):
        clear_content(test)

def setup_or_teardown_failure(suite):
    for kw in tree.get_elements(suite, 'kw'):
        status_tag = tree.get_element(kw, 'status')
        if tree.get_element_attribute(status_tag, 'status') == 'FAIL':
                return True
    return False

def main_func(suite, make_html, errors_and_issues):
    """Checks status of a suite.If failed, parses through testcases and subsuites"""
    if is_failed(suite):
        for sub_suite in tree.get_elements(suite, 'suite'):
                main_func(sub_suite, make_html, errors_and_issues)
        sotf = setup_or_teardown_failure(suite)
        for test in tree.get_elements(suite, 'test'):
            if is_failed(test) or sotf:
                error = tree.get_element_text(tree.get_element(test, 'status'))[:100]
                if not error:
                    error = "Suite teardown failed"
                error = error.replace('\n',' ')
                if error not in errors_and_issues.keys():
                    print("in here")
                    errors_and_issues[error] = list()
                    errors_and_issues[error].append(classify_error(error))
                    errors_and_issues[error].append(tree.get_element_attribute(test, 'name'))
                    errors_and_issues[error].append(tree.get_element_attribute(suite, 'name'))
                    errors_and_issues[error].append(1)
                    continue
                errors_and_issues[error][3] += 1
            elif make_html=='y':
                clear_content(test)
        if make_html=='y':
            for kw in tree.get_elements(suite, 'kw'):
                status_tag = tree.get_element(kw, 'status')
                if tree.get_element_attribute(status_tag, 'status') == 'PASS':
                        suite.remove(kw)
    elif make_html=='y':
        clear_suite(suite)
    return errors_and_issues
 
def classify_error(error_to_classify):
    with open('train.csv', 'r') as csvfile:    
        datareader = csv.reader(csvfile)
        max_common = 0
        matched_issue = None
        for row in datareader:
            if error_to_classify in row[0] or (row[0] in error_to_classify):
                return row[1]
            s0 = error_to_classify.lower()
            s1 = row[0].lower()
            s0List = s0.split(" ")
            s1List = s1.split(" ")
            common_count = len(list(set(s0List)&set(s1List)))
            if common_count>max_common:
                max_common = common_count
                matched_issue = row[1]  
        return matched_issue

def get_issue_table(dict_input):
    tbl = "<table class='statistics' style='width:100%;'>\n<tr>\n<th>ERROR</th>\n<th>ISSUE</th>\n<th>TEST</th>\n<th>SUITE</th>\n</tr>\n" 
    for x in dict_input.keys():
        if type(dict_input[x]) is list:
            tbl += "<tr>\n<td>" + x + "</td>\n" 
            tbl += "<td>" + dict_input[x][0] + "</td>\n"
            tbl += "<td>" + dict_input[x][1] + "</td>\n"
            tbl += "<td>" + dict_input[x][2] + "</td>\n</tr>\n"
    tbl += "</table>"
    return tbl

def get_errors_table(i_e):
    tbl = "<table style='width:100%;'>\n<tr>\n<th>ERROR</th>\n<th>ISSUE</th>\n<th>TEST</th>\n<th>SUITE</th>\n<th>SOURCE</th>\n<th>VERSION</th>\n</tr>\n"
    for e_i in i_e:
        for x in e_i.keys():
            if type(e_i[x]) is list:
                tbl += "<tr>\n<td>" + x + "</td>\n" 
                tbl += "<td>" + e_i[x][0] + "</td>\n"
                tbl += "<td>" + e_i[x][1] + "</td>\n"
                tbl += "<td>" + e_i[x][2] + "</td>\n"
                tbl += "<td>" + e_i['source'] + "</td>\n"
                tbl += "<td>" + e_i['version'] + "</td>\n</tr>\n"
    tbl += "</table>\n"
    return tbl


def is_failed(tag):
    status_tag = tree.get_element(tag, 'status')
    if tree.get_element_attribute(status_tag, 'status') == 'FAIL':
        return True
    return False


def CleanHTML(html_log, errors_and_issues):
    """Removes passed suites/tests, adds error & issue table and the resulting log is saved as 'new.html'"""
    with io.open(html_log, 'rb') as fp:
        soup = BeautifulSoup(fp, "html.parser")

    tags = ['suite', 'test']
    for tag in tags:
        script_tag = soup.find('script', id=tag+"Template")
        template = script_tag.contents[0]
        template = "{{if status=='FAIL'}}\n" + template + "\n{{/if}}"
        script_tag.contents[0].replace_with(template)

    tbl = get_issue_table(errors_and_issues)
    soup.body.append(BeautifulSoup(tbl, 'html.parser'))

    html = soup.prettify("utf-8")
    with open(html_log, "wb") as file:
        file.write(html)

def stats_log(stats, i_e):
    log = "<html>\n<head>\n<style>\n \
            table, td, th {border: 1px solid black;} \
            table {border-collapse: collapse;} \
            th {background-color: #04AA6D; color: white;} \
            </style>\n</head>\n"
    tbl = "<table>\n<tr>\n<th>ISSUE</th>\n<th>COUNT</th>\n<th>%</th></tr>\n" 
    for x in stats.keys():
        if type(stats[x]) is list:
            tbl += "<tr>\n<td>" + x + "</td>\n" 
            tbl += "<td>" + str(stats[x][0]) + "</td>\n"
            tbl += "<td>" + str(stats[x][1]) + "</td>\n</tr>\n"
        else:
            tbl += "<tr><td colspan='3'>Total " + x +"ed tests: " + str(stats[x]) +"</td></tr>\n"
    tbl += "<tr><td colspan='3'>Total no. of tests: " + str(stats['pass']+stats['fail']) +"</td></tr>\n"
    tbl += "</table>\n<br><br><br>"
    log += tbl
    log += get_errors_table(i_e)
    log += "</html>\n"
    stat_html = open("stat.html", 'w')
    stat_html.write(log)
    print("File stat.html created!")


def get_stats(i_e):
    if len(i_e) == 1:
        print(i_e)
        exit()
    count = {'environment issue':[0,0],'automation issue':[0,0],'product issue':[0,0], 'pass':0, 'fail':0}
    total = 0
    for e_i in i_e:
        count['pass'] += e_i['pass']
        count['fail'] += e_i['fail']
        #total += (len(e_i)-2)
        for x in (x for x in e_i.keys() if type(e_i[x]) is list):
            #count[e_i[x][0]][0] += 1
            count[e_i[x][0]][0] += e_i[x][3]
    total = count['environment issue'][0] + count['product issue'][0] + count['automation issue'][0]
    count['environment issue'][1] = str(round(count['environment issue'][0]*100/total,2)) + '%'
    count['product issue'][1] = str(round(count['product issue'][0]*100/total,2)) + '%'
    count['automation issue'][1] = str(round(count['automation issue'][0]*100/total,2)) + '%'
    return count

def is_in_duration(strt_date, date, end_date):
    if strt_date is None and end_date is None:
        return True
    format_str = '%m/%d/%Y' # The format
    start = datetime.datetime.strptime(strt_date, format_str)
    date = datetime.datetime.strptime(date, format_str)
    end = datetime.datetime.strptime(end_date, format_str)
    if start<=date<=end:
        return True
    return False

def get_urls_between(url, strt_date, end_date):
    """ip_date should be in mm/dd/yyyy format"""
    valid_urls = []
    try:
        page = requests.get(url).text
    except ConnectionError as e:    # This is the correct syntax
        return valid_urls
    soup = BeautifulSoup(page, 'html.parser')
    for node in soup.find_all('a')[1:]:
        #if node.get('href').endswith('.xml'):
        if "pabot" not in node.get('href'):
            y = node.previous_sibling
            if y is not None:
                date_regex = re.compile('(\d{1,4}[-/.]\d{1,4}[-/.]\d{1,4})')
                date = date_regex.findall(str(y))[0]
                if is_in_duration(strt_date, date, end_date):
                    valid_urls.append(url.split('.net')[0] + '.net' + node.get('href'))
        #if node.get('href').endswith('/') and "pabot" not in node.get('href'):
            #valid_urls.append(url.split('.net')[0] + '.net' + node.get('href'))
    return valid_urls

def get_file_or_folder(url, ext):
    page = requests.get(url).text
    soup = BeautifulSoup(page, 'html.parser')
    return [url.split('.net')[0] + '.net' + node.get('href') for node in soup.find_all('a') if node.get('href').endswith(ext)]


def get_dir_url(url, dest):
    dirs = re.split('.net' , url)[1]
    fname = dirs.rsplit('/', 1)[1]
    dirs = dirs.rsplit('/', 1)[0]
    directory = os.path.join(dest, dirs)
    if os.path.isdir(directory):
        new_logfile = directory + fname
        tree.save_xml(root, new_logfile)
        html_log = new_logfile[:-3] + '.html'
        robot.rebot(new_logfile, log = html_log, report=None)
        CleanHTML(html_log, e_i) 
    else:
        os.makedirs(directory)


def for_url(url, i_e, exclude_list, strt_date, end_date, make_html, dest, make_report):
    print("here: "+url)
    if url in exclude_list:
        return
    if url.endswith('.xml'):
        print(url) 
        try:
            lxmltree = etree.parse(url)
            root = lxmltree.getroot()
            main_suite = root.find('suite')
        except ConnectionError as e:    # This is the correct syntax
            stats = get_stats(i_e)
            stats_log(stats, i_e)
        except:
            print("Invalid XML file")
            return
        if not is_failed(main_suite):
            print("All suites passed")
            e_i = {}
        else:
            e_i = main_func(main_suite, make_html, {})
            if make_html == 'y':
                dirs = re.split('.net' , url)[1]
                print(dirs)
                new_logfile = 'new_' + re.split(r' |/|\\' , url)[-1]
                print(new_logfile)
                create_html(new_logfile, root, e_i)
                if dest[0:4] == 'http':
                    upload_to_url(new_logfile[:-3] + 'html', dest, dirs)
                    os.remove(new_logfile)
                    os.remove(new_logfile[:-3] + 'html')
        if make_report == 'y':
            e_i = get_info(root, e_i)
            i_e.append(e_i)  
    elif url.endswith('/'):
        for folder in get_urls_between(url, strt_date, end_date):
            for_url(folder, i_e, exclude_list, strt_date, end_date, make_html, dest, make_report)

def upload_to_url(new_logfile, dest, dirs):
    ftp = ftplib.FTP('wpstwork4.vse.rdlabs.hpecorp.net', "wpstuser", "hpvse1")
    dest = re.split('.net', dest)[1] #dest from http://wpstwork4.vse.rdlabs.hpecorp.net/Mythili/systemvet/test1/ to /Mythili/systemvet/test1/
    print(dest)
    ftp.cwd(dest)
    dirs = re.split(r' |/|\\' , dirs)[:-1] #everything except fname.xml [1:]
    for dirr in dirs[1:]: 
        print(dirr)
        if dirr in ftp.nlst():
            ftp.cwd(dirr)
        else:
            loc = ftp.mkd(dirr)
            ftp.cwd(dirr)
    with open(new_logfile, 'rb') as file:
        ftp.storbinary(f"STOR {new_logfile}", file)               # file to send    # send the file
    file.close()

def get_info(root, e_i):
    total_tests = tree.get_elements(root, 'statistics/total/stat')[1]
    e_i['source'] = ''
    for x in tree.get_elements(root, 'suite'):
        source = tree.get_element_attribute(x, 'source')
        if source is not None:
            e_i['source'] =  '-'.join(re.split(r' |/|\\' , source)[-3:-1])
            break
        for subsuites in tree.get_elements(x, 'suite'):
            source = tree.get_element_attribute(subsuites, 'source')
            if source is not None:
                e_i['source'] =  '-'.join(re.split(r' |/|\\' , source)[-3:-1])
                break
    try:
        md = tree.get_child_elements(root, 'suite/metadata')
        e_i['version'] = tree.get_element_text(md[0])
    except AssertionError as e:
        e_i['version'] = ''
        pass
    e_i['pass'] = int(tree.get_element_attribute(total_tests, 'pass'))
    e_i['fail'] = int(tree.get_element_attribute(total_tests, 'fail'))
    for keys in e_i.keys():
        if e_i[keys] is None:
            e_i[keys] = ''
    return e_i

def create_html(new_logfile, root, e_i):
    '''new_logfile should be of the form xx/yy/zz/blah.xml or just blah.xml'''
    tree.save_xml(root, new_logfile)
    html_log = new_logfile[:-3] + 'html'
    robot.rebot(new_logfile, log = html_log, report=None)
    CleanHTML(html_log, e_i) 

def for_file(xml_file, make_html, save_to, make_report):
    fd = open(xml_file, 'r')
    try:
        root = tree.parse_xml(fd)
        main_suite = tree.get_element(root, 'suite')
    except:
        print("Invalid XML File " + xml_file)
        return 
    if not is_failed(main_suite):
        print("All suites passed")
        e_i = {}
    else:
        e_i = main_func(main_suite, make_html, {})
        if make_html=='y':
            #new_logfile = os.path.join(save_to, 'new_' + fname)
            #print(new_logfile)
            if dest[0:4] == 'http':
                fname = 'new_' + re.split(r' |/|\\' , xml_file)[-1]
                create_html(fname, root, e_i)
                upload_to_url(fname[:-3] + 'html', dest, save_to)
                #fname = re.split(r' |/|\\' , save_to)[-1]
                #upload_to_url(new_logfile[:-3]+'html', dest, save_to)
                os.remove(fname[:-3] + 'html')
                os.remove(fname)
            else:
                new_logfile = os.path.join(save_to, re.split(r' |/|\\' , xml_file)[-1])
    if make_report == 'y':
        e_i = get_info(root, e_i)
    return e_i

def difference(each_input, xml_file):
    result1 = ''
    result2 = ''
    maxlen = len(xml_file) if len(each_input)<len(xml_file) else len(each_input)
    for i in range(maxlen):
        letter1 = each_input[i:i+1]
        letter2 = xml_file[i:i+1]
        if letter1 != letter2:
            result2+=letter2
    return result2

def get_path(dest, path):
    fname = re.split(r' |/|\\' , path)[-1]
    if dest[0:4] == 'http':
        #return 'new_' + fname
        return path.replace(fname, '')
    dirs = re.split(r' |/|\\' , path)[:-1] #no -1
    directory = dest
    for x in dirs:
        directory = os.path.join(directory, x)
        if not os.path.isdir(directory):
            os.makedirs(directory)
    new_logfile = os.path.join(directory, fname)
    return new_logfile

if __name__ == '__main__':
    my_parser = argparse.ArgumentParser(description='Remove passed test cases and create statistics for triage')
    my_parser.add_argument('Path',
                        metavar='path',
                        type=str,
                        help='the path to check xml files', nargs='+')
    my_parser.add_argument('-e', '--exclude', type=str, action='store', help='exclude this path', nargs='*')
    my_parser.add_argument('--between', type=str, action='store', help='in this duration', nargs=2)
    args = my_parser.parse_args()
    input_paths = args.Path
    exclude_list = args.exclude
    dates = args.between
    make_html = input("Make an output html FOR EACH xml file with only failed tests? [y/n]:")
    make_report = input("Make a statistics report of all the issues and errors? [y/n]:")
    dest = ''
    if make_html == 'y':
        dest = input("Destination directory to save output log.html: ")
    i_e = []
    if exclude_list is None:
        exclude_list = []
    if dates is None:
        dates = [None, None]
    for each_input in input_paths:
        save_to = ''
        if each_input[0:4] == "http":
            for_url(each_input, i_e, exclude_list, dates[0], dates[1], make_html, dest, make_report)
        elif os.path.isdir(each_input):
            files = glob.iglob(each_input + '/**/*.xml', recursive = True)
            for xml_file in (x for x in files if (x not in exclude_list and not any(exclude in x for exclude in exclude_list))):
                date_mod = time.strftime('%m/%d/%Y', time.gmtime(os.path.getmtime(xml_file)))
                if is_in_duration(dates[0], date_mod, dates[1]):
                    try:
                        if make_html=='y':
                            path = difference(each_input, xml_file)
                            path = get_path(dest, path)
                        e_i = for_file(xml_file, make_html, path, make_report)
                        if e_i is not None:
                            i_e.append(e_i)
                    except AssertionError as e:
                        print("XML file structure issue. Suite wasn't found")
                    except FileNotFoundError as e:
                        print("XML issue. Probably a Pabot output.xml")
        else:
            e_i = for_file(each_input, make_html, get_path(dest,each_input) , make_report) #os.path.join(dest,re.split(r' |/|\\' , each_input)[-1])
            if e_i is not None:
                i_e.append(e_i)
    if make_report == 'y' and not i_e:
        raise AssertionError("All input files seem to be invalid.") 
    if make_report == 'y':
        stats = get_stats(i_e)
        stats_log(stats, i_e)