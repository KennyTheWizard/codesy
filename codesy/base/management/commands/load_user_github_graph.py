from neo4j.v1 import GraphDatabase, basic_auth

from django.core.management.base import BaseCommand
from django.conf import settings

from ...models import User
from gh_gql import User as GithubUser, RepoList


def neo4j_merge_user(user, session):
    statement = """
        MERGE (u:User {id:{id}})
        SET u.name={name}, u.email={email}, u.login={login}
    """
    session.run(statement, user)
    session.sync()


def neo4j_merge_repo(repo, session):
    statement = """
      MERGE (r:Repo {id:{id}})
      SET r.name={name}, r.primaryLanguage={language}, r.owner={owner}
    """
    if 'primaryLanguage' in repo.keys():
        language = repo['primaryLanguage']['name'] if repo['primaryLanguage'] else ""
    else:
        language = u'none'
    session.run(statement, repo, language=language)
    session.sync()


def neo4j_match_repo_relationship(user_id, repo_id, relationship, session):
    statement = """
       MATCH (u:User),(r:Repo) WHERE u.id ='{user}' AND r.id='{repo}'
       CREATE (u)-[:{relation}]->(r)
    """.format(user=user_id, repo=repo_id, relation=relationship)
    session.run(statement)
    session.sync()


def neo4j_merge_languages(user, repos, session):
    for repo in user[repos]:
        # import ipdb; ipdb.set_trace()
        if repo['languages'] == []:
            primaryLanguage = 'none'
        else:
            primaryLanguage = repo['primaryLanguage']['name']
        relationship = """
        MATCH (u),(r)
        WHERE u.id = '%s' AND r.id ='%s' CREATE (u)-[:%s]->(r)
        """ % (
            user['id'], repo['id'], primaryLanguage.upper().replace(" ", "_")
        )
        session.run(relationship)
        session.sync()


class Command(BaseCommand):
    def handle(self, *args, **options):
        driver = GraphDatabase.driver(settings.NEO4J_BOLT_URL, auth=basic_auth(
            settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        session = driver.session()

        # TODO: Figure out a way to not delete the whole graph db every time
        session.run("MATCH (n) DETACH DELETE n")
        test_logins = ['jgmize', 'aprilchomp', 'jdungan', 'jsatt', 'mrmakeit',
                      'groovecoder']
        repo_types = {
            'repositories': 'OWNER',
            'starredRepositories': 'STARRED',
            'contributedRepositories': "CONTRIBUTED"
        }
        for username in test_logins:
            gh_user = GithubUser.get(login=username)['user']
            neo4j_merge_user(gh_user, session)
            for repo_type in repo_types.keys():
                x = 0
                repos = RepoList(type=repo_type, login=username)
                for repo in repos:
                    repo_values = repo['node']
                    x += 1
                    neo4j_merge_repo(repo_values, session)
                    neo4j_match_repo_relationship(gh_user['id'], repo_values['id'], repo_types[repo_type], session)
                print "%s %s : %s " % (username, repo_type, x)

            # neo4j_merge_languages(gh_user, 'contributedRepositories', session)

        session.close()


'''
Recommend repos to a user: i.e., repos that have been starred the most by the users who share stars with this user:
MATCH (u:User)-[:STARRED]->(r)<-[:STARRED]-(u2:User),(u2)-[:STARRED]->(r2)
WHERE NOT (u)-[:STARRED]->(r2)
RETURN  r2.name AS Recommended, count(*) as Strength ORDER BY Strength DESC

Recommended by language
MATCH (u:User{name:"April"}),(r:Repo {primaryLanguage: "JavaScript" })
WHERE NOT (u)-[:CONTRIBUTED]->(r)
RETURN  r.name AS Recommended, count(*) as Strength ORDER BY Strength DESC

'''