__author__ = 'vladimir'

import pymysql
from pymysql import InternalError

from logger import Logger


log = Logger("vksmm.database")


def get_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='',
        db='vksmmdb',
        charset='utf8',
        cursorclass=pymysql.cursors.DictCursor
    )


def update_query(query, params=None, verbose=False):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(query, params)
    except InternalError as e:
        log.error("update_query InternalError: {}\nquery: {}".format(repr(e), query % params))
        return -1
    connection.commit()
    row_id = cursor.lastrowid
    amount = cursor.rowcount
    cursor.close()
    connection.close()
    if verbose:
        log.info("Update Query: last-row-id = {}, total {} row(s) updated".format(row_id, amount))
    return row_id


def select_query(query, params=None, verbose=False):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(query, params)
    except InternalError as e:
        log.error("select_query InternalError: {}\nquery: {}".format(repr(e), query % params))
        return None
    res = cursor.fetchall()
    cursor.close()
    connection.close()
    if verbose:
        log.info("Select Query: {0} row(s) were found, res = {1}".format(len(res), res))
    return res
