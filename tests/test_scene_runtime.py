"""Opt-in installed-runtime contract, using tiny random weights and local assets."""
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get('MEDIA_TEST_SCENE_RUNTIME') == '1',
                     'opt-in installed scene runtime')
class SceneRuntimeTest(unittest.TestCase):
    def test_current_and_legacy_feature_returns(self):
        import sentencepiece
        import torch
        from PIL import Image
        from transformers import (SiglipConfig, SiglipModel, SiglipProcessor,
                                  SiglipImageProcessor, SiglipTokenizer)
        from media_clarity.scenes import Encoder, DIM

        torch.manual_seed(7)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / 'corpus.txt'
            corpus.write_text('a person walks across a bridge\n두 사람이 다리 위에 있다\n', encoding='utf8')
            sentencepiece.SentencePieceTrainer.train(
                input=str(corpus), model_prefix=str(root / 'tokenizer'), vocab_size=64,
                hard_vocab_limit=False, bos_id=-1, eos_id=1, unk_id=0, minloglevel=2)
            tokenizer = SiglipTokenizer(str(root / 'tokenizer.model'))
            SiglipProcessor(SiglipImageProcessor(), tokenizer).save_pretrained(root)
            text = dict(vocab_size=tokenizer.vocab_size, hidden_size=DIM,
                        intermediate_size=64, num_hidden_layers=1, num_attention_heads=12,
                        max_position_embeddings=64, bos_token_id=None, eos_token_id=1,
                        pad_token_id=1)
            vision = dict(hidden_size=DIM, intermediate_size=64, num_hidden_layers=1,
                          num_attention_heads=12, image_size=224, patch_size=16)
            SiglipModel(SiglipConfig(text_config=text, vision_config=vision)).save_pretrained(root)
            picture = io.BytesIO()
            Image.new('RGB', (160, 90), (20, 70, 120)).save(picture, format='JPEG')
            with patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
                encoder = Encoder(root, 'cpu')
                image = encoder.images([{'image': picture.getvalue()}])[0]
                query = encoder.text('두 사람이 다리 위에 있다')
                for result in (image, query):
                    self.assertEqual(len(result), DIM)
                    self.assertAlmostEqual(sum(x*x for x in result), 1, places=5)
                # The old runtime returns these same pooled tensors directly.
                image_features = encoder.model.get_image_features
                text_features = encoder.model.get_text_features
                with patch.object(encoder.model, 'get_image_features',
                                  side_effect=lambda **kw: image_features(**kw).pooler_output), \
                     patch.object(encoder.model, 'get_text_features',
                                  side_effect=lambda **kw: text_features(**kw).pooler_output):
                    self.assertEqual(encoder.images([{'image': picture.getvalue()}])[0], image)
                    self.assertEqual(encoder.text('두 사람이 다리 위에 있다'), query)


if __name__ == '__main__':
    unittest.main()
