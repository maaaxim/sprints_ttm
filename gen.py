# Цель: считать
# 1. Количество выполненных задач.
# 2. Количество проебанных задач + причины проебов


# 3. Показать сколько закрыто задач
# 4. Показать корректность оценки задач

import pandas
import numpy as np
import os
from jira import JIRA
from os.path import join, dirname
from dotenv import load_dotenv


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


dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

JIRA_SERVER = os.environ.get("JIRA_SERVER")
LOGIN = os.environ.get("LOGIN")
PASSWORD = os.environ.get("PASSWORD")

options = {"server": JIRA_SERVER}
jira = JIRA(options, auth=(LOGIN, PASSWORD))

# jql of current sprint
st = 'project = MVM AND issuetype in (Bug, Task, Sub-bug) AND labels = back ' \
     'AND sprint != "Backend Tech Backlog" ' \
     'AND sprint != "Backend Tech Current" ' \
     'AND sprint != "LowOps backlog" ' \
     'AND sprint != "LowOps estimate" ' \
     'AND sprint != "Checkout backlog" ' \
     'AND sprint != "Checkout Estimate" ' \
     'AND sprint != "Polka backlog" ' \
     'AND sprint != "Polka Sprint Estimation" ' \
     'AND sprint != "LKP backlog" ' \
     'AND sprint != "LKP Estimate" ' \
     'AND assignee in (nivanova, ryabukha, borovaya, loboda, sasovets, tsimbalist, vahrameev) ' \
     'AND status not in (Canceled, Closed) ORDER BY status DESC'

issues_all = jira.search_issues(st)

issues_table = []
issues_index = []
for issue in issues_all:

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

        team = get_team(sprint_array['name'])

    # lowops исключить из списка
    if team is "lowops":
        continue

    # 1. проверка факапа разработки - если больше 1 спринта не в тестировании = провалена разработка
    dev_failed = "Нет"
    if len(issue.fields.customfield_10016) > 1 and issue.fields.status.name in {
        "CREATED", "OPEN", "REDO", "READY FOR SPRINT",
        "DEVELOPMENT", "IN REVIEW", "REVIEWING", "WAITING"
    }:
        dev_failed = "Да"

    # 2. проверка ТТМ - если больше 2 спринтов = провален ТТМ
    ttm_failed = "Нет"
    if len(issue.fields.customfield_10016) > 1:
        ttm_failed = "Да"

    issue_item = [
        'https://jira.goods.ru/browse/' + str(issue.key),
        team,
        len(issue.fields.customfield_10016),
        sprint_array['name'],
        issue.fields.status.name,
        dev_failed,
        ttm_failed
    ]

    issues_index.append(issue.key)
    issues_table.append(issue_item)

# Сохраняем в файл
data_frame = pandas.DataFrame(
    np.array(issues_table),
    index=issues_index,
    columns=[
        'Ссылка',
        'Команда',  # Checkout, LKP, Polka
        'Спринтов',  # Считаем только актуальные спринты
        'Спринт',
        'Статус',
        'Разработка просрочена',  # Статус development или более ранний и задача взята в спринт более 5  дней
        'ttm просрочен',  # Более двух спринтов и задача не выкачена
    ]
)

data_frame.to_excel("output.xlsx")
