import torch
import torchvision
import torch.utils.data
import torch.nn as nn
import torch.optim as optim
import torchvision.transforms.functional as F
from graphbook import Graph
from graphbook import step, source, param, resource, event
from graphbook.core.steps import Step
from graphbook.core.utils import image


def get_dataset(train=True, batch_size=64):
    transform = torchvision.transforms.Compose(
        [
            torchvision.transforms.ToTensor(),
            torchvision.transforms.Normalize((0.1307,), (0.3081,)),
        ]
    )

    dataset = torchvision.datasets.MNIST(
        root="./data", train=train, download=True, transform=transform
    )

    dataloader = torch.utils.data.DataLoader(
        dataset, batch_size=batch_size, shuffle=train
    )

    return dataloader


@resource()
@param("device", "string", default="cuda" if torch.cuda.is_available() else "cpu")
def get_device(ctx):
    """
    Returns the device to be used for training. Use "cuda" for GPU and "cpu" for CPU.
    """
    return ctx.device


@step()
@source()
@param("epochs", "number", default=1)
@param("batch_size", "number", default=64)
def get_mnist_train_dataset(ctx):
    """
    Generates the MNIST dataset.

    Args:
        epochs (int): Number of epochs to train the model.
        batch_size (int): Size of each batch of data.
    """
    train_dataloader = get_dataset(train=True, batch_size=ctx.batch_size)

    for _ in range(ctx.epochs):
        for batch in train_dataloader:
            yield {
                "out": [
                    {
                        "batch": batch,
                        "images": [image(F.to_pil_image(img)) for img in batch[0]],
                    }
                ],
            }


def init_get_eval(ctx, **kwargs):
    ctx.curr_step = 0


def evaluate(ctx: Step):
    """
    Evaluates the model on the test dataset and logs the accuracy.
    """
    test_dataloader = get_dataset(train=False)
    model: nn.Module = ctx.model
    model.eval()
    with torch.no_grad():
        correct = 0
        total = 0
        for batch in test_dataloader:
            images, labels = batch
            outputs = model(images.to(ctx.device))
            _, predicted = torch.max(outputs, 1)
            predicted = predicted.cpu()
            correct += (predicted == labels).sum().item()
            total += labels.size(0)
        ctx.log({"accuracy": 100 * correct / total})
    model.train()
    ctx.curr_step += 1


@step()
@param("model", "resource")
@param("device", "resource")
@param("evaluate_every", "number", default=100)
@event("__init__", init_get_eval)
@event("on_end", evaluate)
def get_eval(ctx: Step, _):
    """
    Evaluates the model on start of training, every X steps where X = `evaluate_every`, and on end of training.
    Logs the accuracy each time.

    Args:
        model (nn.Module): The model to be evaluated.
        device (str): The device to be used for evaluation.
        evaluate_every (int): Number of steps between evaluations.
    """
    if ctx.curr_step % ctx.evaluate_every == 0:
        evaluate(ctx)
    ctx.curr_step += 1


@resource("SimpleNN")
@param("device", "resource")
def get_model(ctx):
    """
    Defines a simple feedforward neural network model.
    """

    class SimpleNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = nn.Linear(28 * 28, 128)
            self.fc2 = nn.Linear(128, 10)

        def forward(self, x):
            x = x.view(-1, 28 * 28)
            x = torch.relu(self.fc1(x))
            x = self.fc2(x)
            return x

    model = SimpleNN()
    model.to(ctx.device)
    model.train()

    return model


@resource("SGD")
@param("model", "resource")
@param("learning_rate", "number", default=0.01)
@param("momentum", "number", default=0.9)
def get_optimizer(ctx):
    """
    Uses Stochastic Gradient Descent (SGD) as the optimizer for the model.

    Args:
        model (nn.Module): The model to be optimized.
        learning_rate (float): Learning rate for the optimizer.
        momentum (float): Momentum for the optimizer.
    """
    model: nn.Module = ctx.model
    return optim.SGD(model.parameters(), lr=ctx.learning_rate, momentum=ctx.momentum)


def init_train_step(ctx, **kwargs):
    ctx.curr_step = 0


@step()
@param("model", "resource")
@param("optimizer", "resource")
@param("device", "resource")
@param("log_interval", "number", default=20)
@event("__init__", init_train_step)
def train_step(ctx: Step, data):
    """
    The training step for the MNIST classifier.

    Args:
        model (nn.Module): The model to be trained.
        optimizer (optim.Optimizer): The optimizer to be used for training.
        device (str): The device to be used for training.
        log_interval (int): Number of steps between logging the loss.
    """
    model: nn.Module = ctx.model
    optimizer: optim.Optimizer = ctx.optimizer

    batch = data["batch"]
    images, labels = batch
    optimizer.zero_grad()
    outputs = model(images.to(ctx.device))
    loss = torch.nn.functional.cross_entropy(outputs, labels.to(ctx.device))
    loss.backward()
    optimizer.step()

    if ctx.curr_step > 0 and ctx.curr_step % ctx.log_interval == 0:
        ctx.log({"loss": loss.item()})
    ctx.curr_step += 1


g = Graph()

DOC = """
<div align="center">
    <img src="https://github.com/graphbookai/graphbook/blob/main/docs/_static/graphbook.png?raw=true" alt="Graphbook Logo" height="64">
    <h1 style="margin: 0 0 10px 0">MNIST Classifier</h1>
    <a href="https://github.com/graphbookai/graphbook">
        <img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/graphbookai/graphbook">
    </a>
</div>

This example demonstrates a simple MNIST classifier using PyTorch and Graphbook.

It features:

  * A model with a simple feedforward neural network with one hidden layer.
  * A training step that uses Stochastic Gradient Descent (SGD) as the optimizer.
  * An evaluation step that logs the accuracy of the model on the test dataset.
  * A dataset is loaded using torchvision and transformed to tensors.
"""


@g()
def _():
    g.md(DOC)

    dataset = g.step(get_mnist_train_dataset)
    eval = g.step(get_eval)
    train = g.step(train_step)
    model = g.resource(get_model)
    optimizer = g.resource(get_optimizer)
    device = g.resource(get_device)

    dataset.param("epochs", 1)
    eval.param("device", device)
    eval.param("model", model)
    train.param("device", device)
    train.param("model", model)
    train.param("optimizer", optimizer)
    model.param("device", device)
    optimizer.param("model", model)

    eval.bind(dataset)
    train.bind(eval)


if __name__ == "__main__":
    g.run()

    import time

    try:
        time.sleep(9999)
    except KeyboardInterrupt:
        pass
