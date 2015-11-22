from setuptools import setup, find_packages


version = '0.0.dev0'
tests_require = [
    'unittest2',
    'mock',
    'nose',
    ]


setup(name='htmlhub',
      version=version,
      url="http://github.com/isotoma/htmlhub",
      description="Serve HTML in an authenticated site from github",
      long_description=(
        open("README.rst").read() + "\n" +
        open("CHANGES").read()
        ),
      author="Isotoma Limited",
      author_email="support@isotoma.com",
      license="Apache Software License",
      classifiers=[
          "Intended Audience :: System Administrators",
          "Operating System :: POSIX",
          "License :: OSI Approved :: Apache Software License",
      ],
      packages=find_packages(exclude=['ez_setup']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'PyOpenSSL',
          'service_identity',
          'Twisted',
      ],
      tests_require=tests_require,
      test_suite='nose.collector',
      extras_require={
          'test': tests_require,
          },
      entry_points="""
      [console_scripts]
      htmlhub = htmlhub.server:main
      """
      )
