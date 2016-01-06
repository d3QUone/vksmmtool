__author__ = 'vladimir'

import sys
import time
import traceback
from datetime import datetime
from random import random
import json

import requests
from flask import Flask, render_template, url_for, make_response, redirect, jsonify, request
from logger import Logger

from database import update_query, select_query


reload(sys)
sys.setdefaultencoding('utf8')

# vk app config
CLIENT_ID = "4260316"
CLIENT_SECRET = "x9Qe9JKVfoTG57LMKUgH"


log = Logger("vksmm.backend")
app = Flask("vksmm")
app.config["DEBUG"] = False


def wrap_value(value):
    if isinstance(value, basestring):
        value = value.replace('"', "&quot;").replace("'", "&#39;")
    return value


def unwrap_value(value):
    if isinstance(value, basestring):
        value = value.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    return value


def short_value(value, length):
    if isinstance(value, basestring) and isinstance(length, int):
        if len(value) >= length and length > 3:
            value = value[:length-3] + "..."
    return value


@app.route('/', methods=['GET'])
def landing_page():
    return render_template('landing.html', link=url_for('login_save_h'))


@app.route('/save_h', methods=['GET'])
def login_save_h():
    width = request.args.get('w')
    height = request.args.get('h')
    user_ip = request.remote_addr
    try:
        # TODO: select -> check -> update; don't remove
        update_query(
            "DELETE FROM `screen_size` WHERE `screen_size`.`user_ip`=%s",
            (user_ip, )
        )
        update_query(
            "INSERT INTO `screen_size` (`user_ip`, `w`, `h`) VALUES (%s, %s, %s)",
            (user_ip, width, height)
        )
        # redirect to vk auth then, detailed static params below
        url = "https://oauth.vk.com/authorize?client_id={}&scope=groups&response_type=code&v=5.27&redirect_uri=http://vksmm.info{}".format(CLIENT_ID, url_for('parse_vk_responce'))
        return redirect(url)
    except Exception:
        log.error("/save_h error:\n{}".format(format_exception()))
        return redirect(url_for('landing_page'))


# vk auth module -- OK
@app.route('/vk_login', methods=['GET'])
def parse_vk_responce():
    code = request.args.get('code')
    if code:
        try:
            # render link and get auth_token, user_id
            url = "https://oauth.vk.com/access_token?client_id={}&client_secret={}&code={}&redirect_uri=http://vksmm.info{}".format(CLIENT_ID, CLIENT_SECRET, code, url_for('parse_vk_responce'))
            res = requests.get(url).json()
            user_id = res["user_id"]
            access_token = res["access_token"]

            # LOAD OLD SORTING
            res = select_query(
                "SELECT u.`sort_type` FROM `userinfo` u WHERE u.`user_id`=%s",
                (user_id, )
            )
            try:
                sort_type = res[0][0]
                if sort_type not in ['like', 'repo', 'comm']:
                    sort_type = 'like'
            except:
                sort_type = 'like'

            # LOAD USER-DATA
            try:
                url = "https://api.vk.com/method/execute.name_pic?access_token={0}&id={1}".format(access_token, user_id)
                response = requests.get(url).json()["response"]
                username = response["name"]
                picture = response["picture"]  # avatar 100px
            except Exception as e:
                log.error("load user-datas: {}".format(e))
                username = " "
                picture = None
            log.info("+ {} online".format(username))

            # delete old personal data, save new
            # WTF???
            update_query(
                "DELETE FROM `userinfo` WHERE `userinfo`.`user_id`=%s",
                (user_id, )
            )
            update_query(
                "DELETE FROM `groups` where `groups`.`user_id`=%s",
                (user_id, )
            )
            update_query(
                "INSERT INTO `userinfo` (`user_id`, `auth_token`, `sort_type`, `last_seen`, `username`, `picture`) VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, access_token, sort_type, datetime.now(), username, picture)
            )
            try:
                # load fresh groups from account; 
                req = "https://api.vk.com/method/execute.get_all_groups?access_token={}".format(access_token)
                buf = requests.get(req).json()["response"]

                len_buf = len(buf)
                limit = 100
                steps = len_buf // limit + 1
                for st in range(steps):
                    offset = st * limit
                    i = offset
                    group_ids = ""
                    while i < offset + limit and i < len_buf:
                        group_ids += "{},".format(buf[i])
                        i += 1
                    req = "https://api.vk.com/method/groups.getById?group_ids={0}".format(group_ids[:-1])
                    groups = requests.get(req)
                    groups_json = groups.json()["response"]

                    for item in groups_json:
                        group_name = wrap_value(item["name"])
                        try:
                            update_query(
                                "INSERT INTO `groups` (`user_id`, `group_id`, `screen_name`, `picture`, `added`, `is_old`, `groupname`) VALUES (%s, %s, %s, %s, %s, 0, %s)",
                                (int(user_id), int(item["gid"]), item["screen_name"], item["photo_medium"], int(time.time()), group_name)
                            )
                        except Exception as e:
                            log.error(repr(e))
            except Exception:
                log.error(format_exception())
            return redirect(url_for('index_page', user_id=user_id, access_token=access_token))
        except Exception:
            log.error("/vk_login err:\n{}".format(format_exception()))
    return redirect(url_for('landing_page'))  # add an error-message here ?


# main page
@app.route('/index', methods=['GET'])
def index_page():
    try:
        user_id = int(request.args.get('user_id'))
    except:
        return redirect(url_for('landing_page'))  # add an error-message here ? "'user_id' error: int expected"
    try:
        offset = int(request.args.get('offset'))
    except:
        offset = 0
    sort_type = request.args.get('sort_type')
    access_token = request.args.get('access_token')
    if user_id and access_token:
        try:
            groups = select_query(
                "SELECT g.`group_id`, g.`groupname`, g.`picture` FROM `groups` g WHERE g.`user_id`=%s",
                (user_id, )
            )
            try:
                group_id = int(request.args.get('group_id'))
            except:
                group_id = groups[0][0]

            current_group_name = None
            current_group_picture = None
            group_list = []
            append = group_list.append
            for item in groups:
                buf_group_name = short_value(unwrap_value(item[1]), 30)
                append([item[0], buf_group_name, item[2]])
                if int(item[0]) == int(group_id):
                    current_group_name = unwrap_value(item[1])
                    current_group_picture = item[2]
            if not current_group_name and not current_group_picture:
                # then load from vk
                req = "https://api.vk.com/method/groups.getById?group_ids={0}".format(group_id)
                other_group_data = requests.get(req).json()["response"][0]
                current_group_name = unwrap_value(other_group_data["name"])
                current_group_picture = other_group_data["photo_medium"]

            # UPDATE SORTING
            if sort_type in ('like', 'repo', 'comm'):
                update_query(
                    "UPDATE `userinfo` SET last_seen = %s, sort_type = %s WHERE user_id = %s",
                    (datetime.now(), sort_type, user_id)
                )
            else:
                update_query(
                    "UPDATE `userinfo` SET last_seen = %s WHERE user_id=%s",
                    (datetime.now(), user_id)
                )
                res = select_query(
                    "SELECT u.`sort_type` FROM `userinfo` u WHERE u.`user_id`=%s",
                    (user_id, )
                )
                sort_type = res[0][0]

            try:
                w = int(request.args.get('w'))
                h = int(request.args.get('h'))
            except:
                user_ip = request.remote_addr
                sizes = select_query(
                    "SELECT s.`w`, s.`h` FROM `screen_size` s WHERE s.`user_ip`=%s",
                    (user_ip, )
                )
                w, h = sizes[0]
                log.debug("width = {0}, height = {1}; user_ip = {2}".format(w, h, user_ip))
            try:
                cols = int((w * 0.8 - 235) / 125)  # x
                rows = int((h - 120.0) / 120)  # y
                count = rows * cols
            except:
                count = 35
            posts = select_query(
                "SELECT p.`like`, p.`repo`, p.`comm`, p.`link`, p.`picture` FROM `postinfo` p WHERE p.`group_id`=%s ORDER BY %s DESC LIMIT %s OFFSET %s",
                (group_id, sort_type, count, offset * count)
            )
            if posts:
                recommendation = None
            else:
                max_range = select_query(
                    "SELECT COUNT(g.*) FROM `groups` g WHERE g.`is_old`=1"
                )[0][0]
                try:
                    rlimit = int((h - 300) / 36.0)
                    if rlimit > max_range:
                        log.debug("big screen :)")
                        rlimit = max_range - 1
                except Exception as e:
                    log.error("rlimit e:", e)
                    rlimit = 13
                roffset = int((max_range - rlimit) * random()) + 1
                groups = select_query(
                    "SELECT g.`group_id`, g.`groupname`, g.`picture` FROM `groups` g WHERE g.`is_old`=1 ORDER BY g.`group_id` ASC LIMIT %s OFFSER %s",
                    (rlimit, roffset)
                )
                recommendation = []
                append = recommendation.append
                for item in groups:
                    try:
                        buf_group_name = short_value(unwrap_value(item[1]), 50)
                        if [item[0], buf_group_name, item[2]] not in recommendation:
                            append([item[0], buf_group_name, item[2]])
                    except Exception:
                        log.error(traceback.print_exc())

            # PAGE-NAVIGATION LINKS
            offset_prev = None
            if offset > 0:
                offset_prev = url_for('index_page') + "?user_id={0}&access_token={1}&group_id={2}&offset={3}".format(user_id, access_token, group_id, offset - 1)

            offset_next = None
            count_postinfo = select_query(
                "SELECT COUNT(p.*) FROM `postinfo` p WHERE p.`group_id`=%s",
                (group_id, )
            )[0][0]
            if count * (offset + 1) < count_postinfo:
                offset_next = url_for('index_page') + "?user_id={0}&access_token={1}&group_id={2}&offset={3}".format(user_id, access_token, group_id, offset + 1)

            base_link = url_for('index_page') + "?user_id={0}&access_token={1}&group_id={2}&offset={3}&sort_type=".format(user_id, access_token, group_id, offset)

            # LOAD USER DATA
            user_name, avatar = select_query(
                "SELECT u.`username`, u.`picture` FROM `userinfo` u WHERE u.`user_id`=%s",
                (user_id, )
            )[0]

            # LOAD STATS
            try:
                with open("statistics.txt", "r") as f:
                    stats = json.loads(f.read())
            except:
                stats = None
            return render_template("index.html", group_list=group_list, posts=posts, user_id=user_id,
                                   user_name=user_name, avatar=avatar, access_token=access_token,
                                   current_group_name=current_group_name, current_group_picture=current_group_picture,
                                   offset_prev=offset_prev, offset_next=offset_next, offset=offset, base_link=base_link,
                                   stats=stats, group_id=group_id, count_postinfo=count_postinfo, sort_type=sort_type,
                                   recomendation=recommendation)
        except Exception:
            log.error("Exception at index_page:\n{}".format(format_exception()))
    return redirect(url_for('landing_page'))


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'code': 404, 'error': 'Page not found', 'message': "{0}".format(error)}), 404)


def format_exception():
    """Trace the error in the caught exception"""
    exception_list = traceback.format_stack()
    exception_list = exception_list[:-2]
    exception_list.extend(traceback.format_tb(sys.exc_info()[2]))
    exception_list.extend(traceback.format_exception_only(sys.exc_info()[0], sys.exc_info()[1]))
    exception_str = "Traceback (most recent call last):\n"
    exception_str += "".join(exception_list)
    return exception_str[:-1]


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
