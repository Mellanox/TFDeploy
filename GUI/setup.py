from setuptools import setup

setup(
	name="MLTester",
	version="1.0",
	packages=["mltester"],
	py_modules=["mltester"],
	install_requires=[
		"CommonPyLib>=1.0.2",
	],
	dependency_links = ["git+https://github.com/Mellanox/CommonPyLib.git@master#egg=CommonPyLib-1.0.2"],
	entry_points='''
		[console_scripts]
		ml_tester=MLTester.py:main
		ml_graph_viwer=MLGraphViewer.py:main
	'''
)
