from setuptools import setup, find_packages


version = '0.0.dev0'

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
          'Twisted',
          'PyOpenSSL',
          'service_identity',
      ],
      extras_require={
          'test': ['unittest2', 'mock'],
          },
      entry_points="""
      [console_scripts]
      htmlhub = htmlhub.server:main
      """
      )
