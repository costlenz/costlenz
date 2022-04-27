from aws_cdk import App

from stack.example_stack import CostLenzExampleStack

app = App()

vpc = CostLenzExampleStack(app, "costlenz-example")

app.synth()
