"""Vision Transformer (ViT) classifier for driver state classification.

Supports timm ViT-tiny or MobileViT with a 3-class classification head:
0: alert
1: drowsy
2: yawning
"""

import os
from typing import Dict, List, Optional
import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import transforms


CLASS_NAMES: List[str] = ["alert", "drowsy", "yawning"]


class ViTClassifier(nn.Module):
    """Vision Transformer head for multi-class drowsiness classification."""

    def __init__(
        self,
        checkpoint_path: Optional[str] = None,
        model_name: str = "vit_tiny_patch16_224",
        num_classes: int = 3,
    ) -> None:
        super().__init__()
        self.num_classes = num_classes
        self.device = torch.device(
            "mps"
            if torch.backends.mps.is_available()
            else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.is_loaded = False

        # Image transform pipeline for 224x224 ViT input
        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

        if checkpoint_path and os.path.exists(checkpoint_path):
            try:
                import timm
                self.backbone = timm.create_model(
                    model_name,
                    pretrained=False,
                    num_classes=num_classes,
                )
                state_dict = torch.load(checkpoint_path, map_location=self.device)
                self.backbone.load_state_dict(state_dict)
                self.backbone.to(self.device)
                self.backbone.eval()
                self.is_loaded = True
            except Exception as e:
                self.backbone = None
                self.is_loaded = False
        else:
            self.backbone = None

    def classify_crop(self, roi_bgr: np.ndarray) -> Optional[Dict[str, any]]:
        """Run classification on a cropped ROI frame."""
        if not self.is_loaded or self.backbone is None or roi_bgr is None or roi_bgr.size == 0:
            return None

        try:
            rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
            tensor = self.transform(rgb).unsqueeze(0).to(self.device)

            with torch.no_grad():
                logits = self.backbone(tensor)
                probs = torch.softmax(logits, dim=1).squeeze(0).cpu().numpy()

            predicted_idx = int(np.argmax(probs))
            confidence = float(probs[predicted_idx])
            status = CLASS_NAMES[predicted_idx]

            return {
                "status": status,
                "confidence": confidence,
                "probabilities": {name: float(p) for name, p in zip(CLASS_NAMES, probs)},
            }
        except Exception:
            return None
