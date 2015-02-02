# coding:utf8
from flask import Flask, render_template, url_for, make_response, redirect, jsonify, request, g
from contextlib import closing
from datetime import datetime
import time
import requests
import sqlite3
import json
import os
from random import random
import traceback
import sys

reload(sys) # prepare coding
sys.setdefaultencoding('utf8')

app = Flask(__name__)
app.config.update(
    DATABASE = 'base.db',
    DEBUG = False
)

# run once from bash to auto-setup tables
def init_db():
    with closing(connect_db()) as db:
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


def connect_db():
    return sqlite3.connect(app.config['DATABASE'])


@app.before_request
def before_request():
    g.db = connect_db()


@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


@app.route('/', methods = ['GET'])
def landing_page():
    return render_template('landing.html', link = url_for('login_save_h'))


@app.route('/save_h', methods = ['GET'])
def login_save_h():
    # parse height
    width = request.args.get('w')
    height = request.args.get('h')
    user_IP = request.remote_addr
    try:
        g.db.execute("delete from screen_size where user_ip = '{0}'".format(user_IP))
        g.db.execute("insert into screen_size (user_ip, w, h) values ('{0}', {1}, {2})".format(user_IP, width, height))
        g.db.commit()
        # redirect to vk auth then, detailed static params below
        redirect_uri = "http://vksmm.info" + url_for('parse_vk_responce')
        client_id = "4260316"
        link = "https://oauth.vk.com/authorize?"
        link += "client_id=" + client_id
        link += "&scope=groups"
        link += "&response_type=code&v=5.27"
        link += "&redirect_uri=" + redirect_uri
        return redirect(link)
    except Exception as e:
        print "/save_h error:\n", format_exception(e)
        return redirect(url_for('landing_page'))


# vk auth module -- OK
@app.route('/vk_login', methods = ['GET'])
def parse_vk_responce():
    code = request.args.get('code')
    if code:
        try:
            client_id = "4260316"
            client_secret = "x9Qe9JKVfoTG57LMKUgH"
            redirect_uri = "http://vksmm.info" + url_for('parse_vk_responce')
            # render link and get auth_token, user_id
            req = "https://oauth.vk.com/access_token?"
            req += "client_id=" + client_id
            req += "&client_secret=" + client_secret
            req += "&code=" + code
            req += "&redirect_uri=" + redirect_uri
            res = requests.get(req).json()

            user_id = res["user_id"]
            access_token = res["access_token"]

            # LOAD OLD SORTING
            res = g.db.execute("select sort_type from userinfo where user_id = {0}".format(user_id)).fetchall()
            try:
                sort_type = res[0][0]
                if sort_type not in ['like', 'repo', 'comm']:
                    sort_type = 'like'
            except:
                sort_type = 'like'

            # LOAD USER-DATAS
            try:
                req = "https://api.vk.com/method/execute.name_pic?access_token={0}&id={1}".format(access_token, user_id)
                response = requests.get(req).json()["response"]
                username = response["name"] 
                picture = response["picture"] # avatar 100px
            except Exception as e:
                print "load user-datas:", e
                username = " "
                picture = None
            print "+", username, "online"
            
            # delete old personal data first + save new 
            g.db.execute("delete from userinfo where user_id = {0}".format(user_id))
            g.db.execute("delete from groups where user_id = {0}".format(user_id))
            g.db.execute("insert into userinfo (user_id, auth_token, sort_type, last_seen, username, picture) values ({0}, '{1}', '{2}', '{3}', '{4}', '{5}')".format(int(user_id), access_token, sort_type, datetime.now(), username, picture))
            g.db.commit()

            try:
                # load fresh groups from account; 
                req = "https://api.vk.com/method/execute.get_all_groups?access_token=" + access_token
                buf = requests.get(req).json()["response"]
                
                len_buf = len(buf)
                limit = 100
                steps = len_buf // limit + 1
                for st in range(steps):
                    offset = st*limit
                    i = offset
                    group_ids = ""
                    while i < offset + limit and i < len_buf:
                        group_ids += "{0},".format(buf[i])
                        i += 1

                    req = "https://api.vk.com/method/groups.getById?group_ids={0}".format(group_ids[:-1])
                    groups = requests.get(req)
                    groups_json = groups.json()["response"]

                    for item in groups_json:
                        groupname = item["name"].replace('"', "&quot;").replace("'", "&#39;")
                        try:
                            g.db.execute("insert into groups (user_id, group_id, screen_name, picture, added, is_old, groupname) values ({0}, {1}, '{2}', '{3}', {4}, 0, '{5}')".format(int(user_id), int(item["gid"]), item["screen_name"], item["photo_medium"], int(time.time()), groupname))
                        except:
                            print "sql:", "insert into groups (user_id, group_id, screen_name, picture, added, is_old, groupname) values ({0}, {1}, '{2}', '{3}', {4}, 0, '{5}')".format(int(user_id), int(item["gid"]), item["screen_name"], item["photo_medium"], int(time.time()), groupname)
                    g.db.commit()
            except Exception as e:
                print format_exception(e)                
            return redirect(url_for('index_page', user_id = user_id, access_token = access_token))
        except Exception as e:
            print "/vk_login err:", format_exception(e)
    return redirect(url_for('landing_page')) # add an error-message here ?


# main page
@app.route('/index', methods = ['GET'])
def index_page():
    try:
        user_id = int(request.args.get('user_id'))
    except:
        return redirect(url_for('landing_page')) # add an error-message here ? "'user_id' error: int expected"
    try:
        offset = int(request.args.get('offset'))
    except:
        offset = 0 
    sort_type = request.args.get('sort_type')
    access_token = request.args.get('access_token')
    if user_id and access_token:
        try:
            groups = g.db.execute("select group_id, groupname, picture from groups where user_id = {0}".format(user_id)).fetchall()
            try:
                group_id = int(request.args.get('group_id'))
            except:
                group_id = groups[0][0]
            
            current_group_name = None
            current_group_picture = None
            group_list = []
            append = group_list.append
            for item in groups: 
                buf_group_name = item[1].replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
                if len(buf_group_name) >= 30:
                    buf_group_name = buf_group_name[:27] + "..."
                
                append([item[0], buf_group_name, item[2]])
                if int(item[0]) == int(group_id):
                    current_group_name = item[1].replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
                    current_group_picture = item[2]
            if not current_group_name and not current_group_picture:
                # then load from vk
                req = "https://api.vk.com/method/groups.getById?group_ids={0}".format(group_id)
                other_group_data = requests.get(req).json()["response"][0]
                current_group_name = other_group_data["name"].replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
                current_group_picture = other_group_data["photo_medium"]
            
            # UPDATE SORTING
            if sort_type in ['like', 'repo', 'comm']:
                g.db.execute("update userinfo set sort_type = '{0}', last_seen = '{1}' where user_id = {2}".format(sort_type, datetime.now(), user_id))
                g.db.commit()
            else:
                g.db.execute("update userinfo set last_seen = '{0}' where user_id = {1}".format(datetime.now(), user_id))
                g.db.commit()
                res = g.db.execute("select sort_type from userinfo where user_id = {0}".format(user_id)).fetchall()
                sort_type = res[0][0]

            try:
                w = int(request.args.get('w'))
                h = int(request.args.get('h'))
            except:
                user_IP = request.remote_addr
                sizes = g.db.execute("select w, h from screen_size where user_ip = '{0}'".format(user_IP)).fetchall()
                w, h = sizes[0]
                print "width = {0}, height = {1}; user_ip = {2}".format(w, h, user_IP)
            try:
                cols = int((w*0.8 - 235)/125) #x
                rows = int((h - 120.0)/120)   #y
                count = rows*cols
            except:
                count = 35
            posts = g.db.execute("select like, repo, comm, link, picture from postinfo where group_id = {0} order by {1} desc limit {2} offset {3}".format(group_id, sort_type, count, offset*count)).fetchall()
            if posts:
                recomendation = None
            else:
                max_range = g.db.execute("select count(*) from groups where is_old = 1").fetchall()[0][0]
                try:
                    rlimit = int((h - 300)/36.0)
                    if rlimit > max_range:
                        print "big screen :)"
                        rlimit = max_range - 1
                except Exception as e:
                    print "rlimit e:", e
                    rlimit = 13
                roffset = int((max_range-rlimit)*random()) + 1
                groups = g.db.execute("select group_id, groupname, picture from groups where is_old = 1 order by group_id asc limit {0} offset {1}".format(rlimit, roffset)).fetchall()
                
                recomendation = []
                append = recomendation.append
                for item in groups:
                    try:
                        buf_group_name = item[1].replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
                        if len(buf_group_name) >= 50:
                            buf_group_name = buf_group_name[:47] + "..."
                        if [item[0], buf_group_name, item[2]] not in recomendation:
                            append([item[0], buf_group_name, item[2]])
                    except:
                        pass

            # PAGE-NAVIGATION LINKS
            offset_prev = None
            if offset > 0: 
                offset_prev = url_for('index_page') + "?user_id={0}&access_token={1}&group_id={2}&offset={3}".format(user_id, access_token, group_id, offset - 1)

            offset_next = None
            count_postinfo = g.db.execute("select count(*) from postinfo where group_id = {0}".format(group_id)).fetchall()[0][0]
            if count*(offset + 1) < count_postinfo:
                offset_next = url_for('index_page') + "?user_id={0}&access_token={1}&group_id={2}&offset={3}".format(user_id, access_token, group_id, offset + 1)

            base_link = url_for('index_page') + "?user_id={0}&access_token={1}&group_id={2}&offset={3}&sort_type=".format(user_id, access_token, group_id, offset)

            # LOAD USER DATA
            userdata = g.db.execute("select username, picture from userinfo where user_id = {0}".format(user_id)).fetchall()[0]
            user_name = userdata[0]
            avatar = userdata[1]
            
            # finaly load stats
            try:
                f = open("statistics.txt", "r")
                stats = json.loads(f.read())
                f.close()
            except:
                stats = None            
            return render_template("index.html", group_list = group_list, posts = posts, user_id = user_id, user_name = user_name, avatar = avatar,
                                   access_token = access_token, current_group_name = current_group_name, current_group_picture = current_group_picture,
                                   offset_prev = offset_prev, offset_next = offset_next, offset = offset, base_link = base_link, stats = stats,
                                   group_id = group_id, count_postinfo = count_postinfo, sort_type = sort_type, recomendation = recomendation)
        except Exception as e:
            print "Exception (index_page):\n", format_exception(e)
    return redirect(url_for('landing_page')) 


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'code': 404, 'error': 'Page not found', 'message': "{0}".format(error)}), 404)


# tracing the error in the caugth exception
def format_exception(e):
    exception_list = traceback.format_stack()
    exception_list = exception_list[:-2]
    exception_list.extend(traceback.format_tb(sys.exc_info()[2]))
    exception_list.extend(traceback.format_exception_only(sys.exc_info()[0], sys.exc_info()[1]))
    exception_str = "Traceback (most recent call last):\n"
    exception_str += "".join(exception_list)
    # Removing the last \n
    exception_str = exception_str[:-1]
    return exception_str


if __name__ == '__main__':
    app.run(host='0.0.0.0')
