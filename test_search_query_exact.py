import os
import django
import json

os.environ['DATABASE_URL'] = 'sqlite:///db.sqlite3'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from feedback.views import search_manga_database, _filter_search_results_by_query

query = "Ma'bud minorasi: Ustaxona jangi"
results = search_manga_database(query, limit=50)
print(f"SEARCH RESULTS FROM API (Count: {len(results)}):")
for i, r in enumerate(results[:10]):
    print(f"  {i+1}. {r.get('title')} | URL: {r.get('url')}")

filtered = _filter_search_results_by_query(query, results)
print(f"\nFILTERED RESULTS (Count: {len(filtered)}):")
for i, r in enumerate(filtered[:10]):
    print(f"  {i+1}. {r.get('title')} | URL: {r.get('url')}")
