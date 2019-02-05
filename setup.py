from setuptools import setup

setup(name='ugly_midi',
      version='0.1',
      description='a midi library for personal use',
      author='FX',
      author_email='fxiang@eng.ucsd.edu',
      license='MIT',
      packages=['ugly_midi'],
      install_requires=[
          'numpy >= 1.7.0',
          'mido >= 1.1.16',
      ],
      zip_safe=False)
