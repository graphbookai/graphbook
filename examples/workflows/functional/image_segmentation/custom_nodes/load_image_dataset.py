from graphbook import Note, step, source, param
import os
import os.path as osp


@step("Custom/LoadImageDataset")
@source()
def load_image_dataset(ctx):
    """
    Loads a dataset of images from a directory.

    Args:
        image_dir (str): The directory containing the images
    """
    subdirs = os.listdir(ctx.image_dir)

    def create_note(subdir):
        image_dir = osp.join(ctx.image_dir, subdir)
        return Note(
            {
                "name": subdir,
                "image": [
                    {"value": osp.join(image_dir, img), "type": "image"}
                    for img in os.listdir(image_dir)
                ],
            }
        )

    for subdir in subdirs:
        yield create_note(subdir)
