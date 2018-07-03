from setuptools import setup

setup(
	name="MLTester",
	version="1.0",
	packages=["mltester",
	          "mltester.actions",
	          "mltester.dialogs"],
	package_data={'mltester': ['images/*']},	
	install_requires=[
		"matplotlib",
		"CommonPyLib>=1.0.3",
	],
	dependency_links = ["git+https://github.com/Mellanox/CommonPyLib.git@master#egg=CommonPyLib-1.0.3"],
	entry_points='''
		[console_scripts]
		ml_analyze_nvperf=mltester.ml_analyze_nvperf:main
		ml_analyze_verbs=mltester.ml_analyze_verbs:main
		ml_analyze_trace=mltester.ml_analyze_trace:main
		ml_tester_gui=mltester.ml_tester:main
		ml_graph_viewer=mltester.ml_graph_viewer:main
	'''
)
