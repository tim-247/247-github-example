import json

import requests
import urllib3
from dateutil import parser

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def jiratable(tickets: list) -> str:
    """
    Creates a Jira table for our ticket
    """
    tablestr = ""
    # create header row
    tablestr += "||{0}||\n".format("||".join(i for i in tickets[0].keys()))
    for row in tickets:
        tablestr += "| {0} |\n".format(
            " | ".join(row[key] for key in tickets[0].keys())
        )
    return tablestr


def get_results_paginated(
    session: requests.Session, url: str, jql: str, fields: list
) -> list:
    """
    Gets results from multiple pages of a Jira response.

    * session: A requests.Session object
    * url: The search endpoint for the Jira API. Example:
    https://jira.dev.bbc.co.uk/rest/api/2/search
    * jql: The JQL query to execute on the search endpoint
    * fields: A list of fields to be returned in the query results
    """

    results = []
    max_results = 100

    # count results
    result_count_text = session.get(
        url=url,
        params={
            "jql": jql,
            "maxResults": 0,  # We don't want the results yet, just the count
        },
    ).text
    result_count = int(json.loads(result_count_text)["total"])

    # How many pages will be in the result set
    pages = countpages(max_results, result_count)

    for page in range(pages):  # First page is 0, last page is pages-1
        page_results = session.get(
            url=url,
            params={
                "jql": jql,
                "fields": fields,
                "maxResults": max_results,
                "startAt": max_results * page,  # First result is 0
            },
        ).text
        for result in json.loads(page_results)["issues"]:
            results.append(result)

    return results


def countpages(results_per_page: int, total_results: int) -> int:
    """
    Basic function to count number of pages in a result set.
    Divides total results by results per page, then adds 1 if there is a remainder.
    """
    return (total_results // results_per_page) + (total_results % results_per_page > 0)


def get_duration(startdt: str, enddt: str) -> tuple[int, int, int]:
    td = parser.parse(enddt) - parser.parse(startdt)
    return td.seconds // 3600, (td.seconds // 60) % 60, td.seconds


cert = "/Users/oryant01/.private/BBC-staff-cert-oryant01-20241128.pem"

incidents_jql = "project = OPS and issueFunction in linkedIssuesOf('key = PRB-1966') AND 'Technologies at Fault' is not EMPTY AND status = Closed"  # noqa: E501

session = requests.Session()
session.cert = cert
session.verify = False

incidents = get_results_paginated(
    session, "https://jira.dev.bbc.co.uk/rest/api/2/search", incidents_jql, ["key"]
)

incident_keys = [inc["key"] for inc in incidents]
print(incident_keys)

tickets = []

total_impact_time = 0
total_ops_time = 0

for key in incident_keys:
    r = session.get(f"https://jira.dev.bbc.co.uk/rest/api/2/issue/{key}")
    j = json.loads(r.text)

    if j["fields"]["customfield_16303"]:
        techs = [
            j["fields"]["customfield_16303"][x]["fields"]["summary"]
            for x in range(0, len(j["fields"]["customfield_16303"]))
        ]
    else:
        techs = []

    impact_time = get_duration(
        j["fields"]["customfield_10052"], j["fields"]["customfield_10053"]
    )

    ops_time = get_duration(j["fields"]["created"], j["fields"]["resolutiondate"])

    tickets.append(
        {
            "Key": key,
            "Technology at fault": " ".join(techs),
            "Incident duration": f"{impact_time[0]} hours, {impact_time[1]} minutes",
            "Ops time": f"{ops_time[0]} hours, {ops_time[1]} minutes",
        }
    )

    total_impact_time += impact_time[2]
    total_ops_time += ops_time[2]

print(jiratable(tickets))
print(
    f"Total impact: {total_impact_time // 3600} hours, {total_impact_time // 60 % 60} minutes"
)
print(
    f"Total ops time: {total_ops_time // 3600} hours, {total_ops_time // 60 % 60} minutes"
)
