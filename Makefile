.PHONY: help test clean clean-tools clean-coverage clean-dist\
        lint coverage testall dist dist-upload

project = reel

help:
	@echo "test - run pytest"
	@echo "clean - remove build and runtime files"
	@echo "clean-tools - remove lint and testing files"
	@echo "clean-coverage - remove coverage test files"
	@echo "clean-dist - remove distribution build files"
	@echo "lint - check code for style"
	@echo "coverage - measure how much code the tests cover"
	@echo "testall - shortcut for test/coverage/lint"
	@echo "dist - build a distribution for pypi"
	@echo "dist-upload - upload a distribution to pypi"

test:
	python -m pytest -W ignore

clean-tools:
	find . -type d -name '.pytest_cache' -exec rm -r {} +

clean-coverage:
	rm -f .coverage
	rm -f .coverage.*
	rm -rf etc/htmlcov/

clean-dist:
	find . -type d -name '__pycache__' -exec rm -r {} +
	find . -type d -name 'build' -exec rm -r {} +
	find . -type d -name 'dist' -exec rm -r {} +

clean: clean-coverage clean-tools clean-dist

other_files = sitecustomize.py setup.py

lint:
	python -m flake8 --max-complexity 10 $(project) tests $(other_files)
	python -m pydocstyle $(project) tests $(other_files)
	python -m pylint --disable=R0801 $(project) tests $(other_files)

coverage: clean-coverage
	coverage run --module pytest --doctest-modules $(project)
	coverage run --module pytest -W ignore
	coverage combine
	coverage html -d etc/htmlcov
	coverage report -m

testall: clean lint coverage

dist: clean-dist
	find . -type d -name '$(project).egg-info' -exec rm -r {} +
	python setup.py sdist bdist_wheel
	twine check dist/*

dist-upload: dist
	twine upload dist/*
