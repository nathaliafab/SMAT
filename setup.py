# _*_ coding: UTF-8 _*_

from setuptools import setup


def readme():
    with open('README.md') as f:
        return f.read()


setup(
    name='nimrod',
    description='The killer of useless mutants.',
    log_description=readme(),
    version='2.0.0',
    url='https://github.com/easy-software-ufal/nimrod-hunor',
    author='Marcio Augusto Guimarães',
    author_email='masg@ic.ufal.br',
    license='MIT',
    packages=[
        'nimrod',
        'nimrod.tools',
    ],
    install_requires=[
        'argparse==1.4.0',
        'beautifulsoup4==4.6.0',
        'pygithub==2.5.0',
        'gitpython==3.1.50'
    ],
    test_suite='nose.collector',
    tests_require=[
        'nose',
        'coverage'
    ],
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'nimrod=nimrod.main:main'
        ]
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Topic :: Test :: Mutation :: Java'
    ],
    python_requires='>=3'
)
