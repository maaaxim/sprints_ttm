# @TODO осталось добавить соответствие оценок

import pandas
import numpy as np
import os
import sys
import statistics
from pprint import pprint
from datetime import datetime, timezone
from dateutil import parser
from jira import JIRA, JIRAError
from os.path import join, dirname
from dotenv import load_dotenv


def utc_to_local(utc_dt):
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)


def days_between(d1, d2):
    time_delta = d1 - d2
    return time_delta.days


def get_team(sprint_name):
    if "Checkout" in sprint_name:
        return "checkout"
    elif "Polka" in sprint_name:
        return "polka"
    elif "LKP" in sprint_name:
        return "lkp"
    elif "LowOps" in sprint_name:
        return "lowops"
    else:
        return "wtf"


# Подключаемся к жире
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

JIRA_SERVER = os.environ.get("JIRA_SERVER")
LOGIN = os.environ.get("LOGIN")
PASSWORD = os.environ.get("PASSWORD")

options = {"server": JIRA_SERVER}
jira = JIRA(options, auth=(LOGIN, PASSWORD))

# Получаем аргументы
args = sys.argv[1]
if len(args) <= 1:
    print("Укажите спринт/ы")
    exit()

sprint_ids = args.split(',')

for sprint_id in sprint_ids:
    try:
        sprint = jira.sprint(sprint_id)
        print(sprint.name)
    except JIRAError:
        print(sprint_id + " - скорее всего нет такого спринта")
        exit()

# Строим запрос
st = '(sprint = ' + sprint_ids[0]
if len(sprint_ids) > 0:
    for sprint_id in sprint_ids[1:]:
        st += ' OR sprint = ' + sprint_id
st += ') AND labels = "back" ORDER BY status ASC'

issues_all = jira.search_issues(st, expand='changelog')

issues_table = []
issues_index = []

# Для подсчета медианы
issues_ttms = []

for issue in issues_all:

    changelog = issue.changelog

    # Получим дату закрытия таски (дата статуса closed, последняя в истории)
    closed_date = ''
    for history in changelog.histories:
        for item in history.items:
            if item.field == 'status':
                if item.toString == 'Closed':
                    closed_date = parser.parse(history.created)
                    # print('Date:' + history.created + ' From:' + item.fromString + ' To:' + item.toString)

    # Получим дату взятия в спринт таски (первый спринт, когда добавлена туда)
    start_date = ''
    team = ""
    sprint_array = []
    for sprint_info in issue.fields.customfield_10016:

        # Уберем квадратные скобки и лишнюю хрень
        begin, end = sprint_info.find('['), sprint_info.rfind(']')
        filtered_str = sprint_info[begin + 1: end]

        # Сформируем удобный массив для работы со спринтом
        sprint_array = {}
        split_sprint_info = filtered_str.split(",")
        for part in split_sprint_info:
            part_split = part.split("=")
            sprint_array[part_split[0]] = part_split[1]

        # (количество дней с момента, когда задача впервые добавлена в спринт до закрытия задачи)
        # нас интересует первый спринт с датой начала
        if sprint_array['startDate'] != '<null>':
            start_date = parser.parse(sprint_array['startDate'])
            break

    nowdate = datetime.now()
    gmt_now = utc_to_local(nowdate)
    if closed_date != '':
        ttm = days_between(closed_date, start_date)
        issues_ttms.append(ttm)
    else:
        ttm = days_between(gmt_now, start_date)

    start_date_text = ''
    if start_date != '':
        start_date_text = start_date.strftime('%d-%b-%Y')

    closed_date_text = ''
    if closed_date != '':
        closed_date_text = closed_date.strftime('%d-%b-%Y')

    team = get_team(sprint_array['name'])

    issue_item = [
        'https://jira.goods.ru/browse/' + str(issue.key),
        team,
        sprint_array['name'],
        issue.fields.status.name,
        ttm,
        start_date_text,
        closed_date_text,
    ]

    issues_index.append(issue.key)
    issues_table.append(issue_item)

issues_index.append('Медианное значение')
issues_table.append([
        '',
        'all',
        '',
        '',
        statistics.median(issues_ttms),
        '',
        '',
    ])

# Сохраняем в файл
data_frame = pandas.DataFrame(
    np.array(issues_table),
    index=issues_index,
    columns=[
        'Ссылка',
        'Команда',  # Checkout, LKP, Polka
        'Спринт',
        'Статус',
        'TTM',
        'Взяли',
        'Закрыли',
    ]
)

writer = pandas.ExcelWriter('output.xlsx', engine='xlsxwriter')

data_frame.to_excel(writer, sheet_name='Закрытые')

writer.save()
