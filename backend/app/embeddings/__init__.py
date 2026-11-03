"""Embedding generation for document chunks (Milestone 10D.2).

Everything in this package except `factory.py`'s settings access is
standard-library only on purpose: the provider contract, fingerprinting,
dimension contract, pricing, budget, and the job `processor` are pure
logic that must be testable without a database, network, or paid provider.
Persistence lives in `app.repositories`/`app.services`, never here.
"""
