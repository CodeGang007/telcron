"""The review list tells a signed-in member which reviews are theirs and which they voted helpful
(DEF-031); a visitor sees neither."""

from helpers import API, verified_user

SLUG = "brightbuild-magnet-set"
REVIEW = {"rating": 4, "title": "Strong magnets",
          "body": "Held together well after a month of daily play (DEF-031 list test)."}


async def listed(client, headers=None) -> dict:
    r = await client.get(f"{API}/products/{SLUG}/reviews", headers=headers or {},
                         params={"limit": 50})
    assert r.status_code == 200
    return {item["id"]: item for item in r.json()}


async def test_the_review_list_marks_the_callers_own_review_and_votes(client, db):
    _, _, author = await verified_user(client, "Review Author")
    _, _, voter = await verified_user(client, "Review Voter")
    r = await client.post(f"{API}/products/{SLUG}/reviews", headers=author, json=REVIEW)
    assert r.status_code == 201
    review_id = r.json()["id"]
    assert (await client.post(f"{API}/reviews/{review_id}/helpful",
                              headers=voter)).status_code == 204

    visitor_view = (await listed(client))[review_id]
    assert (visitor_view["mine"], visitor_view["voted"]) == (False, False)

    author_view = (await listed(client, author))[review_id]
    assert (author_view["mine"], author_view["voted"]) == (True, False)

    voter_view = await listed(client, voter)
    assert (voter_view[review_id]["mine"], voter_view[review_id]["voted"]) == (False, True)
    # The vote marks only the review voted on.
    assert not [i for i, item in voter_view.items() if item["voted"] and i != review_id]
