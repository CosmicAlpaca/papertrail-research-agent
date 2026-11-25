from server.agent import merge_papers, metadata_allowed, validate_judgments
from server.providers import abstract_text
from server.schemas import Plan
import pytest

def paper(id='https://openalex.org/W1', title='A detailed paper title on explainability', **kwargs):
    return {'id': id, 'title': title, 'doi': 'https://doi.org/10.123/example', 'year': 2020,
            'abstract': 'We introduce an explainer and evaluate it on molecular graphs.',
            'retracted': False, 'open_access': True, 'provenance': [], 'criteria': [], **kwargs}

def test_duplicate_versions_keep_both_discovery_routes():
    rows=merge_papers([('keyword search',[paper()]),('semantic search',[paper(id='https://openalex.org/W2')])])
    assert len(rows)==1 and len(rows[0]['aliases'])==2
    assert rows[0]['provenance']==['keyword search','semantic search']

def test_citation_expansion_cannot_escape_dates_or_access_filters():
    plan={'year_from':2018,'year_to':2024,'open_access':True}
    assert not metadata_allowed(paper(year=2017),plan)
    assert not metadata_allowed(paper(year=None),plan)
    assert not metadata_allowed(paper(retracted=True),plan)
    assert not metadata_allowed(paper(open_access=False),plan)
    assert metadata_allowed(paper(),plan)

def test_fabricated_model_quote_is_downgraded_to_uncertain():
    rows=[paper()]; criteria=[{'id':'c1','text':'Uses molecular graphs'}]
    raw={'judgments':[{'paper_id':rows[0]['id'],'criterion_id':'c1','status':'supported','quote':'This fabricated quote is not in the source','reason':'claimed support'}]}
    validate_judgments(rows,criteria,raw)
    assert rows[0]['criteria'][0]['status']=='uncertain'
    assert not rows[0]['criteria'][0]['quote_verified']

def test_actual_quote_retains_attribution_without_becoming_human_gold():
    rows=[paper()]; criteria=[{'id':'c1','text':'Uses molecular graphs'}]
    raw={'judgments':[{'paper_id':rows[0]['id'],'criterion_id':'c1','status':'supported','quote':'evaluate it on molecular graphs.','reason':'literal experimental statement'}]}
    validate_judgments(rows,criteria,raw)
    assert rows[0]['criteria'][0]['quote_verified']
    assert rows[0]['criteria'][0]['status']=='supported'

def test_abstract_reconstruction_rejects_unbounded_positions():
    assert abstract_text({'Hello':[0],'world':[1],'bad':[100000]})=='Hello world'

def test_invalid_date_range_and_duplicate_criteria_are_rejected():
    with pytest.raises(ValueError): Plan(question='Find research',queries=['research'],year_from=2024,year_to=2020)
    with pytest.raises(ValueError): Plan(question='Find research',queries=['research'],criteria=[{'id':'a','text':'Requirement 1'},{'id':'a','text':'Requirement 2'}])

def test_rrf_cannot_overrule_the_neural_reranker_by_score_scale(monkeypatch):
    from server import agent
    wrong = paper(id='w',title='A frequently retrieved but indirect match',doi=None)
    right = paper(id='r',title='The specific method satisfying the question',doi=None)
    monkeypatch.setattr(agent,'neural_scores',lambda *args:[-8.0,-5.0])
    monkeypatch.setattr(agent,'event',lambda *args,**kwargs:None)
    state={'run_id':'test','request':{'plan':{'question':'A specific method'},'rerank':True},
           'lists':[('q1',[wrong,right]),('q2',[wrong]),('q3',[wrong])],
           'repaired':False,'ablations':{},'candidate_index':{}}
    agent.rank(state)
    assert state['papers'][0]['id']=='r'
