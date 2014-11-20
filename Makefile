test:
	py.test --flakes --pep8 ldf_server --doctest-modules

server:
	python ldf_server/wsgi.py
