#!/usr/bin/env python2.5
# -*- coding: utf-8 -*-

# Copyright (C) 2011 emijrp
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import os
import re
import subprocess
import sys
import urllib
import urllib2

# todo:
# curonly and all history (curonly si puede acumular varias peticiones en un solo GET, ara full history pedir cada pagina una a una)
# usar api o parsear html si no está disponible
# http://www.mediawiki.org/wiki/Manual:Parameters_to_Special:Export

def cleanHTML(raw=''):
    if re.search('<!-- bodytext -->', raw): #<!-- bodytext --> <!-- /bodytext --> <!-- start content --> <!-- end content -->
        raw = raw.split('<!-- bodytext -->')[1].split('<!-- /bodytext -->')[0]
    elif re.search('<!-- start content -->', raw):
        raw = raw.split('<!-- start content -->')[1].split('<!-- end content -->')[0]
    else:
        print 'This wiki doesn\'t use marks to split contain'
        sys.exit()
    return raw

def getAllPageTitles(domain='', namespaces=[]):
    #http://en.wikipedia.org/wiki/Special:AllPages
    #http://archiveteam.org/index.php?title=Special:AllPages
    #http://www.wikanda.es/wiki/Especial:Todas
    if not domain:
        print 'Please, use --domain parameter'
        sys.exit()
    
    #namespace checks and stuff
    namespacenames = {0:''} # main is 0, no prefix
    if namespaces:
        raw = urllib.urlopen('%s?title=Special:Allpages' % (domain)).read()
        m = re.compile(r'<option [^>]*?value="(?P<namespaceid>\d+)"[^>]*?>(?P<namespacename>[^<]+)</option>').finditer(raw) # [^>]*? to include selected="selected"
        if 'all' in namespaces:
            namespaces = []
            for i in m:
                namespaces.append(int(i.group("namespaceid")))
                namespacenames[int(i.group("namespaceid"))] = i.group("namespacename")
        else:
            #check if those namespaces really exist in this wiki
            namespaces2 = []
            for i in m:
                if int(i.group("namespaceid")) in namespaces:
                    namespaces2.append(int(i.group("namespaceid")))
                    namespacenames[int(i.group("namespaceid"))] = i.group("namespacename")
            namespaces = namespaces2
    else:
        namespaces = [0]
    
    #retrieve all titles from Special:Allpages, if the wiki is big, perhaps there are sub-Allpages to explore
    namespaces = [i for i in set(namespaces)] #uniques
    titles = []
    for namespace in namespaces:
        print '    Retrieving titles in the namespace', namespace
        url = '%s?title=Special:Allpages&namespace=%s' % (domain, namespace)
        raw = urllib.urlopen(url).read()
        raw = cleanHTML(raw)
        
        r_title = r'title="(?P<title>[^>]+)">'
        r_suballpages = r'&amp;from=(?P<from>[^>]+)&amp;to=(?P<to>[^>]+)">'
        deep = 3 # 3 is the current deep of English Wikipedia for Special:Allpages, 3 levels
        c = 0
        checked_suballpages = []
        rawacum = ''
        while re.search(r_suballpages, raw) and c < deep:
            #load sub-Allpages
            m = re.compile(r_suballpages).finditer(raw)
            for i in m:
                fr = i.group('from')
                to = i.group('to')
                name = '%s-%s' % (fr, to)
                if not name in checked_suballpages:
                    checked_suballpages.append(name)
                    url = '%s?title=Special:Allpages&namespace=%s&from=%s&to=%s' % (domain, namespace, fr, to) #do not put urllib.quote in fr or to
                    raw2 = urllib.urlopen(url).read()
                    raw2 = cleanHTML(raw2)
                    rawacum += raw2 #merge it after removed junk
                    print '    Detected sub-Allpages:', name, len(raw2), 'bytes', len(re.findall(r_title, raw2))
            c += 1
        
        m = re.compile(r_title).finditer(rawacum)
        for i in m:
            if not i.group('title').startswith('Special:'):
                if not i.group('title') in titles:
                    titles.append(i.group('title'))
    return titles

def getHeader(domain=''):
    #get the header of a random page, to attach it in the complete XML backup
    #similar to: <mediawiki xmlns="http://www.mediawiki.org/xml/export-0.3/" xmlns:x....
    randomtitle = 'AMF5LKE43MNFGHKSDMRTJ'
    xml = getXML(domain=domain, title=randomtitle)
    header = xml.split('</mediawiki>')[0]
    return header

def getXML(domain='', title='', curonly=False):
    #http://www.mediawiki.org/wiki/Manual_talk:Parameters_to_Special:Export#Parameters_no_longer_in_use.3F
    limit = 1
    title_ = re.sub(' ', '_', title)
    tempfilename = 'tempxmlfile.xml'
    tempfilename2 = 'tempxmlfile2.xml'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.8.0.4) Gecko/20060508 Firefox/1.5.0.4'}
    params = {'title': 'Special:Export', 'pages': title, 'action': 'submit', }
    if curonly:
        params['curonly'] = 1
    else:
        params['offset'] = 1
        params['limit'] = limit
    params = urllib.urlencode(params)
    req = urllib2.Request(url=domain, data=params, headers=headers)
    f = urllib2.urlopen(req)
    xml = f.read()

    #if complete history, check if this page history has > 1000 edits, if so, retrieve all using offset
    if not curonly:
        xml2 = xml
        while len(re.findall(r'<revision>', xml2)) == limit:
            #try to retrieve more, although perhaps it is exact 1000 edits
            params['offset'] = re.findall(r'<timestamp>([^<]+)</timestamp>', xml2)[-1][0]
            req2 = urllib2.Request(url=domain, data=params, headers=headers)
            f2 = urllib2.urlopen(req2)
            xml2 = f2.read()
            xml = xml.split('</page>')[0]+xml2.split('<page>\n')[1]
            print len(xml2), re.findall('<timestamp>[^<]+</timestamp>', xml2)
    return xml

def cleanXML(xml=''):
    xml = xml.split('</siteinfo>\n')[1]
    xml = xml.split('</mediawiki>')[0]
    return xml

if __name__ == '__main__':
    domain = 'http://archiveteam.org/index.php' # 'http://en.wikipedia.org/w'
    #domain = 'http://wikanda.cadizpedia.eu/w/index.php' # 'http://en.wikipedia.org/w'
    curonly = False
    namespaces = [0]
    
    if re.findall(r'(wikipedia|wikisource|wiktionary|wikibooks|wikiversity|wikimedia|wikispecies|wikiquote|wikinews)\.org', domain):
        print 'DO NOT USE THIS SCRIPT TO DOWNLOAD WIKIMEDIA PROJECTS!\nDownload the dumps from http://download.wikimedia.org\nThanks!'
        sys.exit()
    
    #get titles
    print 'Loading page titles from namespaces =', ','.join([str(i) for i in namespaces])
    titles = getAllPageTitles(domain=domain, namespaces=namespaces)
    #print '\n'.join(titles)
    print '%d titles loaded' % (len(titles))
    
    #get xml
    print 'Retrieving the XML for every title'
    header = getHeader(domain=domain)
    footer = '</mediawiki>'
    xmlfilename = 'wikidump-%s.xml' % (str(datetime.datetime.now()))
    xmlfile = open(xmlfilename, 'w')
    xmlfile.write(header)
    for title in titles:
        xml = getXML(domain=domain, title=title, curonly=curonly)
        xml = cleanXML(xml=xml)
        xmlfile.write(xml)
        break
    xmlfile.write(footer)
    xmlfile.close()