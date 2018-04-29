from setuptools import setup

setup(
	name="MLTester",
	version="1.0",
	packages=["mltester",
                  "mltester.actions",
                  "mltester.dialogs"],
	install_requires=[
		"matplotlib",
		"CommonPyLib>=1.0.2",
	],
	dependency_links = ["git+https://github.com/Mellanox/CommonPyLib.git@master#egg=CommonPyLib-1.0.2"],
	entry_points='''
		[console_scripts]
		ml_tester_gui=mltester.ml_tester:main
	'''
)
