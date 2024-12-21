# -*- encoding: utf-8 -*-
'''
@File    :   downloader.py
@Time    :   2021/06/27 10:24:10
@Author  :   olixu
@Version :   1.0
@Contact :   273601727@qq.com
@WebSite    :   https://blog.oliverxu.cn
------------
degui.liu 2024.12.22 修改下载超时和文件名异常的问题
'''

# here put the import lib
from __future__ import print_function, unicode_literals
import os
import sys
import time
import random
import json
import shutil
from collections import defaultdict
from urllib.parse import quote
import requests
from lxml import etree
import fitz
from PyInquirer import style_from_dict, Token, prompt
from requests.exceptions import Timeout, RequestException

def main():
    """
    下载学位论文入口程序：

    调用方式：python downloader.py --pages '1-2' --major '计算机'
    """
    answers = search_arguments()
    info_url, pages = arguments_extract(answers)
    papers = download_main_info(info_url, pages)
    will_download = confirmation(papers)['confirmation']
    if will_download:
        paper_download(papers)
    else:
        print('Bye!')

def paper_download(papers):
    jpg_dir = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime()) + "".join(random.sample('zyxwvutsrqponmlkjihgfedcba23429837498234',5))
    for paper in papers:
        print(100*'@')
        paper_filename = paper['year'] + '_' + paper['filename'] + '_' + paper['author'] + '_' + paper['mentor'] + '.pdf'
        # 如果文件名中有特殊字符，移除或替换它们
        paper_filename = paper_filename.replace(":", "_").replace(" ", "_").replace("/", "_")
        if verify_name(paper_filename):
            print("论文{}已经存在".format(paper_filename))
            continue
        print("正在下载论文：", paper['filename'])
        init(jpg_dir=jpg_dir)
        try:
            download_jpg(paper['link'], jpg_dir=jpg_dir)
            merge_pdf(paper_filename, jpg_dir=jpg_dir)
        except Exception as e:
            print(e)

def search_arguments():
    style = style_from_dict({
                Token.Separator: '#cc5454',
                Token.QuestionMark: '#673ab7 bold',
                Token.Selected: '#cc5454',  # default
                Token.Pointer: '#673ab7 bold',
                Token.Instruction: '',  # default
                Token.Answer: '#f44336 bold',
                Token.Question: '',
                })

    questions = [
        {
            'type': 'list',
            'message': '请选择检索方式',
            'name': 'choose_key',
            'choices': [
                '主题',
                '题名',
                '关键词',
                '作者',
                '院系',
                '专业',
                '导师',
                '年份'

            ]
        },
        {
            'type': 'list',
            'message': '请选择检索硕士或博士论文',
            'name': 'xuewei',
            'choices': [
                '硕士',
                '博士',
                '硕士及博士'
            ]
        },
        {
            'type': 'list',
            'message': '请选择排序方式',
            'name': 'px',
            'choices': [
                '按题名字顺序排序',
                '按学位年度倒排序'
            ]
        },
        {
            'type': 'input',
            'name': 'content',
            'message': '请输入你的检索词'
        },
        {
            'type': 'input',
            'name': 'page',
            'message': '请输入想要检索的页面范围，一页20篇论文'
            # 这里需要添加validate关键字
        }
    ]
    answers = prompt(questions, style=style)
    return answers

def arguments_extract(answers):
    choose_key = {'主题':'topic', '题名':'title', '关键词':'keyword', '作者':'author', '院系':'department', '专业':'subject', '导师':'teacher', '年份':'year'}
    xuewei = {'硕士及博士':'0', '博士':'1', '硕士':'2'}
    px = {'按题名字顺序排序':'1', '按学位年度倒排序':'2'}
    info_url = "http://thesis.lib.sjtu.edu.cn/sub.asp?content={}&choose_key={}&xuewei={}&px={}&page=".format(quote(answers['content']), \
        choose_key[answers['choose_key']], \
        xuewei[answers['xuewei']], \
        px[answers['px']])
    print(info_url)
    pages = answers['page'].split('-')
    pages = [int(pages[0]), int(pages[1])]
    return info_url, pages

def confirmation(papers):
    print("\033[\033[1;32m 检索到了以下{}篇文章\033[0m".format(len(papers)))
    for i in papers:
        print('\033[1;31m 题目\033[0m', i['filename'], '\033[1;34m 作者\033[0m', i['author'], '\033[1;36m 导师\033[0m', i['mentor'], '\033[1;35m 年份\033[0m', i['year'])
        # 这里需要格式化输出对其一下
    questions = [
        {
            'type': 'confirm',
            'message': "确认下载{}篇文章吗？".format(len(papers)),
            'name': 'confirmation',
            'default': 'True'
        }
    ]
    answers = prompt(questions)
    return answers

def verify_name(paper_filename):
    if not os.path.exists('./papers'):
        os.mkdir('./papers')
    if paper_filename in os.listdir('./papers'):
        return True
    return False

def init(jpg_dir):
    """初始化文件夹路径
    """
    try:
        shutil.rmtree('./{}/'.format(jpg_dir))
        print("删除本地{}文件夹".format(jpg_dir))
    except Exception as e:
        print(e)
    try:
        os.mkdir('./{}/'.format(jpg_dir))
        print("新建本地{}文件夹".format(jpg_dir))
    except Exception as e:
        print(e)

def download_main_info(info_url: str, pages: list):
    papers = []
    info_url = info_url
    headers = {
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36'
    }
    result = requests.Session()
    for page in range(pages[0], pages[1]+1):
        print("正在抓取第{}页的info".format(page))
        info_url_construction = info_url + str(page)
        response = result.get(info_url_construction, headers=headers, allow_redirects=False)
        html = etree.HTML(response.content, etree.HTMLParser())
        for i in range(2, 22):
            # 有些是论文保密，所以link需要错误处理
            info_dict = defaultdict(str)
            try:
                filename = html.xpath('/html/body/section/div/div[3]/div[2]/table/tr[{}]//td[2]/text()'.format(i))[0]
                author = html.xpath('/html/body/section/div/div[3]/div[2]/table/tr[{}]/td[3]/div/text()'.format(i))[0]
                mentor = html.xpath('/html/body/section/div/div[3]/div[2]/table/tr[{}]/td[6]/div/text()'.format(i))[0]
                year = html.xpath('/html/body/section/div/div[3]/div[2]/table/tr[{}]/td[8]/div/text()'.format(i))[0]
                link = "http://thesis.lib.sjtu.edu.cn/" + html.xpath('/html/body/section/div/div[3]/div[2]/table/tr[{}]/td[9]/div/a[2]/@href'.format(i))[0]
                info_dict['filename'] = filename
                info_dict['author'] = author
                info_dict['mentor'] = mentor
                info_dict['year'] = year
                info_dict['link'] = link
                papers.append(info_dict)
            except Exception as e:
                #print(e)
                pass
    print("总共抓取到{}个元数据信息".format(len(papers)))
    return papers

def download_jpg(url: str, jpg_dir: str, timeout=10, retries=3):
    """下载论文链接为jpg，并添加了超时处理、重试机制和更详细的日志。
        :param url: 阅读全文链接
        :param timeout: 请求超时时间（秒）
        :param retries: 每个请求的最大重试次数
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36'
    }
    result = requests.Session()
    print("开始获取图片地址")

    try:
        # 使用timeout参数来限制每个请求的最大等待时间
        response = result.get(url, headers=headers, allow_redirects=False, timeout=timeout)
        url = response.headers['Location']
        response = result.get(url, headers=headers, allow_redirects=False, timeout=timeout)
        url = response.headers['Location']
        response = result.get(url, headers=headers, allow_redirects=False, timeout=timeout)
        url_bix = response.headers['Location'].split('?')[1]
        url = "http://thesis.lib.sjtu.edu.cn:8443/read/jumpServlet?page=1&" + url_bix
        response = result.get(url, headers=headers, allow_redirects=False, timeout=timeout)
        urls = json.loads(response.content.decode())
        print("已经获取到图片地址")

        i = 1
        while True:
            fig_url = "http://thesis.lib.sjtu.edu.cn:8443/read/" + urls['list'][0]['src'].split('_')[0] + "_{0:05d}".format(i) + ".jpg"

            for attempt in range(retries + 1):  # 尝试重试
                try:
                    response = result.get(fig_url, headers=headers, timeout=timeout)

                    if len(response.content) < 2000 and len(response.content) != 1049:
                        # 如果内容过小，可能是无效的图片文件，重试
                        print(f"页面 {i} 内容异常小，尝试重试...")
                        continue

                    if len(response.content) == 1049:
                        print("资源无法访问了，网站挂了")
                        break

                    with open('./{}/{}.jpg'.format(jpg_dir, i), 'wb') as f:
                        f.write(response.content)
                    print(f"成功采集第{i}页")
                    i += 1
                    break  # 成功后退出重试循环

                except Timeout:
                    print(f"请求页面 {i} 超时，尝试重试 ({attempt + 1}/{retries})...")
                    if attempt == retries:
                        print(f"页面 {i} 请求多次超时，跳过此页.")
                        i += 1
                    time.sleep(1)  # 等待1秒再重试，减少服务器压力
                    continue

                except RequestException as e:
                    print(f"请求页面 {i} 发生错误: {e}")
                    if attempt == retries:
                        print(f"页面 {i} 请求多次失败，跳过此页.")
                        i += 1
                    time.sleep(1)  # 等待1秒再重试，减少服务器压力
                    continue

            else:  # 如果所有重试都失败了，退出循环
                break

    except Timeout:
        print("初始化请求超时，无法继续下载.")
    except RequestException as e:
        print(f"发生错误: {e}")

def merge_pdf(paper_filename, jpg_dir):
    print(f"paper_filename={paper_filename}, jpg_dir={jpg_dir}")
    doc = fitz.open()  # 创建一个新的空PDF文档
    img_path = './{}/'.format(jpg_dir)

    if len(os.listdir(img_path)) < 80:  # 检查是否有足够的图片以避免下载错误
        print("文章{}下载错误，跳过".format(paper_filename))
        shutil.rmtree(img_path)  # 清理临时目录
        return

    for img in sorted(os.listdir(img_path), key=lambda x: int(x[:-4])):
        try:
            img_file = os.path.join(img_path, img)
            img_rect = fitz.Rect(0, 0, 595, 842)  # A4纸张大小
            img_doc = fitz.open(img_file)  # 打开图像文件
            img_width, img_height = img_doc[0].rect.width, img_doc[0].rect.height
            if img_width < 100 or img_height < 100:  # 如果图像过小，跳过该图像
                print(f"跳过尺寸异常的图片: {img_file}")
                continue
            pdf_bytes = img_doc.convert_to_pdf()  # 将图像转换为PDF格式
            img_pdf = fitz.open("pdf", pdf_bytes)  # 打开刚刚创建的PDF
            page = doc.new_page(width=img_rect.width, height=img_rect.height)  # 在PDF中创建新的空白页
            page.show_pdf_page(page.rect, img_pdf, 0)  # 将图像PDF的第一页显示在新页上
        except Exception as e:
            print(f"处理图像时出错: {img_file}, 错误信息: {e}")
            continue  # 跳过当前图像

    filename = './papers/' + paper_filename
    doc.save(filename)  # 保存合并后的PDF文件
    doc.close()
    print(f"合并完成{filename}", filename)
    shutil.rmtree(img_path)  # 清理临时目录

if __name__=='__main__':
    main()
